import hashlib
import hmac
import io
import json
import re
import time

import pytest
from PIL import Image

from app_factory import create_app
from core.accounts import get_effective_plan, get_user_by_email
from core.subscriptions import get_subscription


PRO_MONTHLY = "pri_01m1dbrhgvk2cb2h87x5g9fcpw"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "test-client-token")
    return create_app().test_client()


def csrf(page):
    match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
    assert match
    return match.group(1).decode()


def register(client, email="member@example.com", password="a secure password"):
    page = client.get("/register")
    return client.post("/register", data={"email": email, "password": password, "csrf_token": csrf(page)})


def image_upload(name="source.png"):
    data = io.BytesIO()
    Image.new("RGB", (12, 12), "white").save(data, format="PNG")
    return io.BytesIO(data.getvalue()), name


def signed_event(event_type="subscription.activated", event_id="evt_activate", status="active"):
    payload = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-09-01T00:00:00Z" if status == "active" else "2026-09-02T00:00:00Z",
        "data": {
            "id": "sub_account" if event_type != "transaction.completed" else None,
            "subscription_id": "sub_account" if event_type == "transaction.completed" else None,
            "customer_id": "ctm_account",
            "customer": {"email": "member@example.com"},
            "custom_data": {"user_id": get_user_by_email("member@example.com")["id"], "email": "member@example.com"},
            "status": status,
            "items": [{"price": {"id": PRO_MONTHLY}}],
            "current_billing_period": {"ends_at": "2099-10-01T00:00:00Z"},
        },
    }
    raw = json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = hmac.new(b"test-webhook-secret", f"{timestamp}:".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"Paddle-Signature": f"ts={timestamp};h1={signature}", "Content-Type": "application/json"}


def test_register_login_logout_and_csrf(client):
    assert client.post("/register", data={}).status_code == 400
    response = register(client)
    assert response.status_code == 302
    assert get_user_by_email("MEMBER@example.com")["credits_balance"] == 10
    assert client.get("/account").status_code == 200
    account_page = client.get("/account")
    assert client.post("/logout", data={"csrf_token": csrf(account_page)}).status_code == 302
    assert client.get("/account").status_code == 401
    login_page = client.get("/login")
    assert client.post("/login", data={"email": "member@example.com", "password": "a secure password", "csrf_token": csrf(login_page)}).status_code == 302


def test_plan_gating_and_free_batch_limit(client):
    assert client.post("/api/v2/convert", data={"tool": "pdf-booklet"}, content_type="multipart/form-data").status_code == 401
    register(client)
    assert client.post("/api/v2/convert", data={"tool": "pdf-booklet"}, content_type="multipart/form-data").status_code == 403
    files = [image_upload(f"source-{index}.png") for index in range(4)]
    response = client.post("/api/v2/convert", data={"tool": "image-to-jpg", "files": files}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_success_consumes_one_credit_but_failed_conversion_does_not(client):
    register(client)
    before = get_user_by_email("member@example.com")["credits_balance"]
    successful = client.post("/api/v2/convert", data={"tool": "image-to-jpg", "files": image_upload()}, content_type="multipart/form-data")
    assert successful.status_code == 200
    assert get_user_by_email("member@example.com")["credits_balance"] == before - 1
    failed = client.post("/api/v2/convert", data={"tool": "image-to-jpg", "files": (io.BytesIO(b"not an image"), "broken.png")}, content_type="multipart/form-data")
    assert failed.status_code == 400
    assert get_user_by_email("member@example.com")["credits_balance"] == before - 1


def test_signed_paddle_activation_is_idempotent_and_cancel_preserves_credits(client):
    register(client)
    raw, headers = signed_event()
    assert client.post("/paddle/webhook", data=raw, headers=headers).status_code == 200
    assert client.post("/paddle/webhook", data=raw, headers=headers).status_code == 200
    assert get_user_by_email("member@example.com")["credits_balance"] == 110
    cancel_raw, cancel_headers = signed_event("subscription.canceled", "evt_cancel", "canceled")
    assert client.post("/paddle/webhook", data=cancel_raw, headers=cancel_headers).status_code == 200
    assert get_subscription("sub_account")["status"] == "canceled"
    assert get_user_by_email("member@example.com")["credits_balance"] == 110
    assert get_effective_plan(get_user_by_email("member@example.com")["id"]) == "free"


def test_transaction_completed_for_the_same_period_does_not_grant_credits_twice(client):
    register(client)
    raw, headers = signed_event("subscription.activated", "evt_activate")
    assert client.post("/paddle/webhook", data=raw, headers=headers).status_code == 200
    completed_raw, completed_headers = signed_event("transaction.completed", "evt_completed")
    assert client.post("/paddle/webhook", data=completed_raw, headers=completed_headers).status_code == 200
    assert get_user_by_email("member@example.com")["credits_balance"] == 110


def test_checkout_custom_data_is_only_rendered_for_authenticated_user(client):
    anonymous = client.get("/pricing?lang=en")
    assert b"data-user-id" not in anonymous.data
    assert b"disabled" in anonymous.data
    register(client)
    authenticated = client.get("/pricing?lang=en")
    assert b"data-user-id" in authenticated.data
    with open("static/js/app.js", encoding="utf-8") as script:
        assert "customData: { user_id: checkoutUserId, email: checkoutEmail }" in script.read()