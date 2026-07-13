"""Auth: Login-only vs. Registrierung, Token-Einmaligkeit."""
from .conftest import register


def test_login_unknown_email_does_not_create_account(client):
    r = client.post("/api/auth/request-link", json={"email": "tippfehler@x.ch"})
    assert r.status_code == 404
    assert "Neu hier" in r.json()["detail"]


def test_link_path_never_creates_accounts(client):
    """Die Registrierungs-Hintertuer ist zu: auch MIT register-Flag kein Konto
    (Konten entstehen nur ueber /register mit AGB/Honeypot/IP-Limit)."""
    r = client.post(
        "/api/auth/request-link",
        json={"email": "hintertuer@test.ch", "register": True, "display_name": "X"},
    )
    assert r.status_code == 404


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
    register(client, "once@test.ch", name="Once")
    r = client.post("/api/auth/request-link", json={"email": "once@test.ch"})
    token = r.json()["dev_token"]
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 400
