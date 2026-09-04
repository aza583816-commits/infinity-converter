"""Account, entitlement, and credit persistence for authenticated users."""

import re
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import abort, g, session
from werkzeug.security import check_password_hash, generate_password_hash

from core.subscriptions import _connection, ensure_subscription_table


FREE_CREDITS = 10
PLAN_LIMITS = {
    "free": {"max_file_mb": 10, "max_files": 3},
    "pro": {"max_file_mb": 100, "max_files": 20},
    "business": {"max_file_mb": 200, "max_files": 50},
}
PREMIUM_TOOL_IDS = frozenset({
    "pdf-booklet", "lms-pdf-size-optimizer", "assignment-cover-page",
    "omr-bubble-sheet", "bulk-certificate-maker", "social-media-image-resizer",
    "quote-social-graphic", "csv-merge-deduplicate", "lms-question-bank-formatter",
})
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class EmailAlreadyExistsError(ValueError):
    """Raised when an address is already owned by an account."""


def canonical_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return 3 <= len(email) <= 254 and bool(EMAIL_PATTERN.fullmatch(email))


def ensure_account_tables() -> None:
    """Create new tables and add subscription ownership without rewriting data."""
    ensure_subscription_table()
    with _connection() as (connection, _):
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    credits_balance INTEGER NOT NULL DEFAULT 10,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS credit_ledger (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
        finally:
            cursor.close()


def create_user(email: str, password: str) -> dict:
    ensure_account_tables()
    email = canonical_email(email)
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": generate_password_hash(password),
        "credits_balance": FREE_CREDITS,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            try:
                cursor.execute(
                    f"INSERT INTO users (id, email, password_hash, credits_balance, created_at) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    tuple(user.values()),
                )
            except Exception as exc:
                if "unique" in str(exc).lower() or "duplicate key" in str(exc).lower():
                    raise EmailAlreadyExistsError from exc
                raise
        finally:
            cursor.close()
    return user


def get_user(user_id: str | None) -> dict | None:
    if not user_id:
        return None
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT id, email, password_hash, credits_balance, created_at FROM users WHERE id = {placeholder}", (user_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()
    return dict(zip(("id", "email", "password_hash", "credits_balance", "created_at"), row)) if row else None


def get_user_by_email(email: str | None) -> dict | None:
    return _get_user_by("email", canonical_email(email)) if email else None


def _get_user_by(column: str, value: str) -> dict | None:
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT id, email, password_hash, credits_balance, created_at FROM users WHERE {column} = {placeholder}", (value,))
            row = cursor.fetchone()
        finally:
            cursor.close()
    return dict(zip(("id", "email", "password_hash", "credits_balance", "created_at"), row)) if row else None


def authenticate(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    return user if user and check_password_hash(user["password_hash"], password) else None


def get_effective_plan(user_id: str | None) -> str:
    if not user_id:
        return "free"
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT plan_tier, status, current_period_end FROM subscriptions WHERE user_id = {placeholder} ORDER BY latest_event_time DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
    if not row or row[1] != "active" or not _period_is_current(row[2]):
        return "free"
    return row[0]


def get_latest_subscription_for_user(user_id: str) -> dict | None:
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT plan_tier, status, current_period_end FROM subscriptions WHERE user_id = {placeholder} ORDER BY latest_event_time DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
    return dict(zip(("plan_tier", "status", "current_period_end"), row)) if row else None


def _period_is_current(period_end: str | None) -> bool:
    if not period_end:
        return False
    try:
        return datetime.fromisoformat(period_end.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return False


def grant_credits_once(user_id: str, event_id: str, delta: int, reason: str) -> bool:
    """Atomically record a billing grant, applying it only for a new event ID."""
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"INSERT INTO credit_ledger (event_id, user_id, delta, reason, created_at) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) ON CONFLICT(event_id) DO NOTHING",
                (event_id, user_id, delta, reason, datetime.now(timezone.utc).isoformat()),
            )
            if cursor.rowcount != 1:
                return False
            cursor.execute(f"UPDATE users SET credits_balance = credits_balance + {placeholder} WHERE id = {placeholder}", (delta, user_id))
            return cursor.rowcount == 1
        finally:
            cursor.close()


def consume_credit(user_id: str) -> bool:
    ensure_account_tables()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(f"UPDATE users SET credits_balance = credits_balance - 1 WHERE id = {placeholder} AND credits_balance > 0", (user_id,))
            return cursor.rowcount == 1
        finally:
            cursor.close()


def csrf_token() -> str:
    return session.setdefault("csrf_token", secrets.token_urlsafe(32))


def verify_csrf(token: str | None) -> bool:
    expected = session.get("csrf_token")
    return bool(token and expected and secrets.compare_digest(token, expected))


def login_user(user: dict) -> None:
    session.clear()
    session["user_id"] = user["id"]
    csrf_token()


def logout_user() -> None:
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "current_user", None):
            return abort(401)
        return view(*args, **kwargs)
    return wrapped