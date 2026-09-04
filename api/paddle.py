"""Paddle Billing webhook endpoint.

This endpoint persists subscription facts only; entitlement enforcement remains
intentionally separate from existing conversion, credit, and authentication code.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from core.limiter import limiter
from core.accounts import get_user, get_user_by_email, grant_credits_once
from core.subscriptions import upsert_subscription


logger = logging.getLogger(__name__)
paddle_bp = Blueprint("paddle", __name__)

PRICE_TO_TIER = {
    "pri_01m1dbrhgvk2cb2h87x5g9fcpw": "pro",
    "pri_01m1dbvw1gydkj7ayvx2vt5sw7": "pro",
    "pri_01m1dc0c192gye7yyhhfkpcc13": "business",
    "pri_01m1dc28fr8rsv3jfyg3jp0qcp": "business",
}
SUPPORTED_EVENTS = {
    "subscription.created", "subscription.activated", "subscription.updated",
    "subscription.canceled", "transaction.completed",
}
VALID_STATUSES = {"active", "past_due", "canceled", "paused"}
WEBHOOK_MAX_AGE_SECONDS = 300


def _signature_is_valid(header: str | None, raw_body: bytes, secret: str) -> bool:
    if not header or not secret:
        return False
    values: dict[str, list[str]] = {}
    for pair in header.split(";"):
        key, separator, value = pair.strip().partition("=")
        if separator and key and value:
            values.setdefault(key, []).append(value)
    timestamps = values.get("ts", [])
    signatures = values.get("h1", [])
    if len(timestamps) != 1 or not signatures:
        return False
    try:
        timestamp = int(timestamps[0])
    except ValueError:
        return False
    if abs(time.time() - timestamp) > WEBHOOK_MAX_AGE_SECONDS:
        return False
    signed_payload = f"{timestamp}:".encode("ascii") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def _event_time(event: dict) -> str:
    occurred_at = event.get("occurred_at")
    if isinstance(occurred_at, str) and occurred_at:
        return occurred_at
    return datetime.now(timezone.utc).isoformat()


def _price_id(data: dict) -> str | None:
    items = data.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict):
            price = item.get("price")
            if isinstance(price, dict) and isinstance(price.get("id"), str):
                return price["id"]
            if isinstance(item.get("price_id"), str):
                return item["price_id"]
    return None


def _email(data: dict) -> str | None:
    customer = data.get("customer")
    if isinstance(customer, dict) and isinstance(customer.get("email"), str):
        return customer["email"]
    if isinstance(data.get("customer_email"), str):
        return data["customer_email"]
    return None


def _event_user(data: dict) -> dict | None:
    custom_data = data.get("custom_data")
    customer_email = _email(data)
    if isinstance(custom_data, dict) and isinstance(custom_data.get("user_id"), str):
        user = get_user(custom_data["user_id"])
        custom_email = custom_data.get("email")
        if user and isinstance(customer_email, str) and isinstance(custom_email, str) and user["email"] == customer_email.lower() == custom_email.lower():
            return user
    return get_user_by_email(customer_email)


def _subscription_from_event(event: dict) -> dict | None:
    event_type = event.get("event_type")
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    subscription_id = data.get("id") if event_type.startswith("subscription.") else data.get("subscription_id")
    customer_id = data.get("customer_id")
    event_id = event.get("event_id")
    price_id = _price_id(data)
    if not all(isinstance(value, str) and value for value in (subscription_id, customer_id, event_id, price_id)):
        return None
    plan_tier = PRICE_TO_TIER.get(price_id)
    if not plan_tier:
        logger.warning("Rejected Paddle event with unknown price ID: event_id=%s", event_id)
        raise ValueError("unknown price ID")
    status = data.get("status") if event_type != "transaction.completed" else "active"
    if status not in VALID_STATUSES:
        return None
    billing_period = data.get("current_billing_period")
    current_period_end = billing_period.get("ends_at") if isinstance(billing_period, dict) else None
    return {
        "subscription_id": subscription_id,
        "customer_id": customer_id,
        "user_email": _email(data),
        "user_id": None,
        "plan_tier": plan_tier,
        "status": status,
        "current_period_end": current_period_end if isinstance(current_period_end, str) else None,
        "latest_event_id": event_id,
        "latest_event_time": _event_time(event),
    }


@paddle_bp.post("/paddle/webhook")
@limiter.exempt
def paddle_webhook():
    raw_body = request.get_data(cache=True)
    if not _signature_is_valid(
        request.headers.get("Paddle-Signature"), raw_body, os.getenv("PADDLE_WEBHOOK_SECRET", "")
    ):
        logger.warning("Rejected Paddle webhook with invalid signature")
        return jsonify(error="Invalid webhook signature."), 401
    try:
        event = json.loads(raw_body)
    except (TypeError, json.JSONDecodeError):
        return jsonify(error="Invalid webhook payload."), 400
    if not isinstance(event, dict) or event.get("event_type") not in SUPPORTED_EVENTS:
        return jsonify(received=True), 200
    try:
        subscription = _subscription_from_event(event)
    except ValueError:
        return jsonify(error="Unsupported Paddle price."), 400
    if not subscription:
        logger.warning("Rejected malformed Paddle event: event_id=%s", event.get("event_id"))
        return jsonify(error="Invalid subscription event."), 400
    user = _event_user(event["data"])
    if user:
        subscription["user_id"] = user["id"]
        subscription["user_email"] = user["email"]
    upsert_subscription(subscription)
    if user and event["event_type"] in {"subscription.created", "subscription.activated", "subscription.updated", "transaction.completed"} and subscription["status"] == "active":
        grant_key = f"subscription-credit:{subscription['subscription_id']}:{subscription['current_period_end'] or subscription['latest_event_id']}"
        grant_credits_once(
            user["id"], grant_key,
            100 if subscription["plan_tier"] == "pro" else 1000,
            f"paddle_{subscription['plan_tier']}",
        )
    return jsonify(received=True), 200