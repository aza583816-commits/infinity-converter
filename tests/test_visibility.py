import pytest

from app_factory import create_app


@pytest.fixture
def hidden_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("PUBLIC_AUTH_ENABLED", "0")
    monkeypatch.setenv("PUBLIC_BILLING_ENABLED", "0")
    return create_app().test_client()


def test_auth_pages_are_hidden_by_default(hidden_client):
    assert hidden_client.get("/register").status_code == 404
    assert hidden_client.get("/login").status_code == 404
    assert hidden_client.get("/account").status_code in (401, 404)


def test_pricing_is_hidden_by_default_and_not_in_sitemap(hidden_client):
    assert hidden_client.get("/pricing").status_code == 404
    sitemap = hidden_client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert b"<loc>https://infinityconverter.com/pricing</loc>" not in sitemap.data


def test_auth_and_billing_can_be_reenabled_without_removing_code(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("PUBLIC_AUTH_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_BILLING_ENABLED", "1")
    client = create_app().test_client()
    assert client.get("/register").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/pricing").status_code == 200
