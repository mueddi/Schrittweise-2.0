"""Auth: Login-only vs. Registrierung, Token-Einmaligkeit."""
from .conftest import register


def test_login_unknown_email_does_not_create_account(client):
    r = client.post("/api/auth/request-link", json={"email": "tippfehler@x.ch"})
    assert r.status_code == 404
    assert "Neu hier" in r.json()["detail"]


def test_register_then_login_works(client):
    headers = register(client, "mia@test.ch", name="Mia")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Mia"

    # danach klappt Login OHNE register-Flag
    r = client.post("/api/auth/request-link", json={"email": "mia@test.ch"})
    assert r.status_code == 200
    assert r.json()["dev_token"]


def test_magic_token_single_use(client):
    r = client.post(
        "/api/auth/request-link",
        json={"email": "once@test.ch", "register": True, "display_name": "Once"},
    )
    token = r.json()["dev_token"]
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 400
