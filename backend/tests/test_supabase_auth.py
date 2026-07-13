"""Supabase-Auth: Login-Mail via Supabase und Token-Tausch gegen App-JWT."""
import pytest

from app.config import settings
from app.routers import auth as auth_router

from .conftest import register


@pytest.fixture()
def supabase_on(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "test-anon-key")


def test_request_link_sends_via_supabase(client, supabase_on, monkeypatch):
    sent = {}

    def fake_send(email, redirect_to):
        sent.update(email=email, redirect_to=redirect_to)
        return True

    register(client, "mia@test.ch", name="Mia")
    monkeypatch.setattr(auth_router, "send_magic_link_via_supabase", fake_send)
    r = client.post("/api/auth/request-link", json={"email": "mia@test.ch"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent"] is True
    # Kein Dev-Token-Leak, obwohl MAGIC_LINK_DEV_RETURN in der Test-Env aktiv ist
    assert body["dev_token"] is None
    assert sent["email"] == "mia@test.ch"
    assert sent["redirect_to"].endswith("/login/verify")


def test_verify_supabase_exchanges_token(client, supabase_on, monkeypatch):
    register(client, "mia@test.ch", name="Mia")
    monkeypatch.setattr(auth_router, "send_magic_link_via_supabase", lambda *a, **k: True)
    client.post("/api/auth/request-link", json={"email": "mia@test.ch"})

    monkeypatch.setattr(
        auth_router, "get_verified_email", lambda tok: "mia@test.ch" if tok == "sb-ok" else None
    )
    ok = client.post("/api/auth/verify-supabase", json={"access_token": "sb-ok"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]
    assert ok.json()["user"]["display_name"] == "Mia"

    bad = client.post("/api/auth/verify-supabase", json={"access_token": "sb-bad"})
    assert bad.status_code == 400


def test_verify_supabase_unknown_account(client, supabase_on, monkeypatch):
    # E-Mail ist bei Supabase verifiziert, aber es gibt kein App-Konto -> 404 statt Geisterkonto
    monkeypatch.setattr(auth_router, "get_verified_email", lambda tok: "ghost@test.ch")
    r = client.post("/api/auth/verify-supabase", json={"access_token": "sb-ok"})
    assert r.status_code == 404


def test_supabase_rate_limit_maps_to_429(client, supabase_on, monkeypatch):
    def fake_send(email, redirect_to):
        raise auth_router.SupabaseRateLimited()

    register(client, "mia@test.ch", name="Mia")
    monkeypatch.setattr(auth_router, "send_magic_link_via_supabase", fake_send)
    r = client.post("/api/auth/request-link", json={"email": "mia@test.ch"})
    assert r.status_code == 429
