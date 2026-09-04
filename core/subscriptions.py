"""Portable persistence for Paddle subscription events."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote


DEFAULT_DATABASE_URL = "sqlite:///instance/infinity_converter.db"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _add_user_id_column(cursor) -> None:
    """Use a savepoint so a PostgreSQL duplicate-column error stays recoverable."""
    cursor.execute("SAVEPOINT subscription_user_id")
    try:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN user_id TEXT")
    except Exception as exc:
        if "duplicate column" not in str(exc).lower() and "already exists" not in str(exc).lower():
            raise
        cursor.execute("ROLLBACK TO SAVEPOINT subscription_user_id")
    finally:
        cursor.execute("RELEASE SAVEPOINT subscription_user_id")


@contextmanager
def _connection():
    database_url = _database_url()
    if database_url.startswith("sqlite:///"):
        raw_path = unquote(database_url.removeprefix("sqlite:///"))
        database_path = Path(raw_path)
        if not database_path.is_absolute():
            database_path = Path.cwd() / database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        try:
            yield connection, "?"
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return

    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url.removeprefix("postgres://")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError("DATABASE_URL must be a SQLite or PostgreSQL URL.")

    import psycopg

    connection = psycopg.connect(database_url)
    try:
        yield connection, "%s"
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_subscription_table() -> None:
    """Create the additive subscription table if it has not been created yet."""
    with _connection() as (connection, _):
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    user_email TEXT,
                    user_id TEXT,
                    plan_tier TEXT NOT NULL CHECK (plan_tier IN ('pro', 'business')),
                    status TEXT NOT NULL CHECK (status IN ('active', 'past_due', 'canceled', 'paused')),
                    current_period_end TEXT,
                    latest_event_id TEXT NOT NULL,
                    latest_event_time TEXT NOT NULL
                )
                """
            )
            _add_user_id_column(cursor)
        finally:
            cursor.close()


def upsert_subscription(subscription: dict) -> None:
    """Persist the newest known Paddle event for one subscription."""
    ensure_subscription_table()
    columns = (
        "subscription_id", "customer_id", "user_email", "user_id", "plan_tier", "status",
        "current_period_end", "latest_event_id", "latest_event_time",
    )
    values = tuple(subscription.get(column) if column == "user_id" else subscription[column] for column in columns)
    with _connection() as (connection, placeholder):
        placeholders = ", ".join([placeholder] * len(columns))
        updates = ", ".join(
            f"{column} = excluded.{column}" for column in columns if column != "subscription_id"
        )
        query = f"""
            INSERT INTO subscriptions ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(subscription_id) DO UPDATE SET {updates}
            WHERE excluded.latest_event_time >= subscriptions.latest_event_time
        """
        cursor = connection.cursor()
        try:
            cursor.execute(query, values)
        finally:
            cursor.close()


def get_subscription(subscription_id: str) -> dict | None:
    """Return one stored subscription for internal verification and tests."""
    ensure_subscription_table()
    with _connection() as (connection, placeholder):
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT subscription_id, customer_id, user_email, user_id, plan_tier, status,
                       current_period_end, latest_event_id, latest_event_time
                FROM subscriptions WHERE subscription_id = {placeholder}
                """,
                (subscription_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
    if not row:
        return None
    keys = (
        "subscription_id", "customer_id", "user_email", "user_id", "plan_tier", "status",
        "current_period_end", "latest_event_id", "latest_event_time",
    )
    return dict(zip(keys, row))