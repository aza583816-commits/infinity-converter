import hashlib
import hmac
import json
import sqlite3
import time

import pytest

from app_factory import create_app
from core.accounts import create_user, get_user
from core.subscriptions import ensure_subscription_table, get_subscription, upsert_subscription


PRO_MONTHLY = "pri_01m1dbrhgvk2cb2h87x5g9fcpw"
PRO_YEARLY = "pri_01m1dbvw1gydkj7ayvx2vt5sw7"
BUSINESS_MONTHLY = "pri_01m1dc0c192gye7yyhhfkpcc13"
BUSINESS_YEARLY = "pri_01m1dc28fr8rsv3jfyg3jp0qcp"


@pytest.fixture
def paddle_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'subscriptions.db'}")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "test-webhook-secret")
    return create_app().test_client()


def paddle_event(price_id=PRO_MONTHLY, event_type="subscription.created", event_id="evt_123", user_id=None):
    data = {
        "id": "sub_123",
        "customer_id": "ctm_123",
        "customer": {"email": "member@example.com"},
        "status": "active",
        "items": [{"price": {"id": price_id}}],
        "current_billing_period": {"ends_at": "2026-10-01T00:00:00Z"},
    }
    if event_type == "transaction.completed":
        data["subscription_id"] = data.pop("id")
    if user_id:
        data["custom_data"] = {"user_id": user_id, "email": "member@example.com"}
    return {"event_id": event_id, "event_type": event_type, "occurred_at": "2026-09-01T00:00:00Z", "data": data}


def signed_headers(payload, timestamp=None, secret="test-webhook-secret"):
    timestamp = timestamp or int(time.time())
    raw_payload = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), f"{timestamp}:".encode() + raw_payload, hashlib.sha256).hexdigest()
    return raw_payload, {"Paddle-Signature": f"ts={timestamp};h1={signature}", "Content-Type": "application/json"}


def test_webhook_accepts_valid_signature_and_upserts_subscription(paddle_client):
    user = create_user("member@example.com", "a secure password")
    raw_payload, headers = signed_headers(paddle_event(user_id=user["id"]))
    response = paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers)
    assert response.status_code == 200
    stored = get_subscription("sub_123")
    assert stored["plan_tier"] == "pro"
    assert stored["user_email"] == "member@example.com"
    assert stored["user_id"] == user["id"]
    assert get_user(user["id"])["credits_balance"] == 110


def test_webhook_does_not_associate_mismatched_custom_data_user(paddle_client):
    create_user("member@example.com", "a secure password")
    other = create_user("other@example.com", "another secure password")
    raw_payload, headers = signed_headers(paddle_event(user_id=other["id"]))
    assert paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers).status_code == 200
    assert get_subscription("sub_123")["user_id"] != other["id"]
    assert get_user(other["id"])["credits_balance"] == 10


def test_webhook_rejects_invalid_signature(paddle_client):
    raw_payload, headers = signed_headers(paddle_event(), secret="wrong-secret")
    assert paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers).status_code == 401
    assert get_subscription("sub_123") is None


def test_webhook_rejects_old_timestamp(paddle_client):
    raw_payload, headers = signed_headers(paddle_event(), timestamp=int(time.time()) - 301)
    assert paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers).status_code == 401
    assert get_subscription("sub_123") is None


def test_webhook_rejects_unknown_price(paddle_client):
    raw_payload, headers = signed_headers(paddle_event(price_id="pri_unknown"))
    assert paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers).status_code == 400
    assert get_subscription("sub_123") is None


def test_webhook_handles_completed_transaction(paddle_client):
    raw_payload, headers = signed_headers(
        paddle_event(price_id=BUSINESS_YEARLY, event_type="transaction.completed", event_id="evt_transaction")
    )
    assert paddle_client.post("/paddle/webhook", data=raw_payload, headers=headers).status_code == 200
    stored = get_subscription("sub_123")
    assert stored["plan_tier"] == "business"
    assert stored["status"] == "active"


def test_subscription_upsert_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'subscriptions.db'}")
    subscription = {
        "subscription_id": "sub_123", "customer_id": "ctm_123", "user_email": None,
        "plan_tier": "pro", "status": "active", "current_period_end": None,
        "latest_event_id": "evt_123", "latest_event_time": "2026-09-01T00:00:00Z",
    }
    upsert_subscription(subscription)
    upsert_subscription(subscription)
    assert get_subscription("sub_123")["latest_event_id"] == "evt_123"


def test_additive_subscription_migration_preserves_existing_record(tmp_path, monkeypatch):
    database = tmp_path / "subscriptions.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE subscriptions (subscription_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, user_email TEXT, plan_tier TEXT NOT NULL, status TEXT NOT NULL, current_period_end TEXT, latest_event_id TEXT NOT NULL, latest_event_time TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("sub_existing", "ctm_existing", "existing@example.com", "pro", "active", None, "evt_existing", "2026-09-01T00:00:00Z"),
        )
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    ensure_subscription_table()
    stored = get_subscription("sub_existing")
    assert stored["customer_id"] == "ctm_existing"
    assert stored["user_id"] is None


def test_pricing_has_real_price_ids_and_uses_selected_billing(monkeypatch):
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "test_client_token")
    page = create_app().test_client().get("/pricing?lang=en")
    assert page.status_code == 200
    for price_id in (PRO_MONTHLY, PRO_YEARLY, BUSINESS_MONTHLY, BUSINESS_YEARLY):
        assert price_id.encode() in page.data
    assert b"https://cdn.paddle.com/paddle/v2/paddle.js" in page.data
    assert b"data-paddle-checkout" in page.data
    with open("static/js/app.js", encoding="utf-8") as script:
        assert "selectedBilling" in script.read()


def test_pricing_disables_paid_checkout_without_client_token(monkeypatch):
    monkeypatch.delenv("PADDLE_CLIENT_TOKEN", raising=False)
    page = create_app().test_client().get("/pricing?lang=en")
    assert page.data.count(b"data-paddle-checkout") == 2
    assert page.data.count(b"data-paddle-checkout data-price-monthly=") == 2
    assert page.data.count(b" disabled>") == 2