"""Passwort-Login: Registrierung, Anmeldung, Fehlerfälle."""


def test_register_logs_in_directly(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["user"]["display_name"] == "Mia"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_login_with_correct_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    r = client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "drei-worte-merken"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_or_unknown_email(client):
    client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "falsch-falsch"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ghost@test.ch", "password": "drei-worte-merken"}).status_code == 401


def test_register_duplicate_email_conflicts(client):
    client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    r = client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "anderes-passwort1", "display_name": "Mia2"},
    )
    assert r.status_code == 409


def test_register_short_password_rejected(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "kurz", "display_name": "Mia"},
    )
    assert r.status_code == 422


def test_passwordless_legacy_account_can_set_password(client):
    # Alt-Konto aus der Magic-Link-Zeit (ohne Passwort, nie eingeloggt)
    client.post(
        "/api/auth/request-link",
        json={"email": "alt@test.ch", "register": True, "display_name": "Alt"},
    )
    r = client.post(
        "/api/auth/register",
        json={"email": "alt@test.ch", "password": "jetzt-mit-passwort", "display_name": "Alt"},
    )
    assert r.status_code == 200, r.text
    assert client.post("/api/auth/login", json={"email": "alt@test.ch", "password": "jetzt-mit-passwort"}).status_code == 200
