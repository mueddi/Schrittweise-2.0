"""Passwort-Login: Registrierung, Anmeldung, Fehlerfälle, Rate-Limit, Passwort ändern."""
from app.routers.auth import LOGIN_FAIL_MAX
from app.security import create_access_token


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


def test_login_rate_limit_blocks_after_too_many_failures(client):
    client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    for _ in range(LOGIN_FAIL_MAX):
        r = client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "falsch-falsch"})
        assert r.status_code == 401
    # Limit erreicht: auch das KORREKTE Passwort wird jetzt abgewiesen (429)
    r = client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "drei-worte-merken"})
    assert r.status_code == 429
    # Andere E-Mail bleibt unbetroffen
    client.post(
        "/api/auth/register",
        json={"email": "ben@test.ch", "password": "drei-worte-merken", "display_name": "Ben"},
    )
    assert client.post("/api/auth/login", json={"email": "ben@test.ch", "password": "drei-worte-merken"}).status_code == 200


def test_login_success_resets_failure_counter(client):
    client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    for _ in range(LOGIN_FAIL_MAX - 1):
        client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "falsch-falsch"})
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "drei-worte-merken"}).status_code == 200
    # Zaehler zurueckgesetzt: erneute Fehlversuche starten wieder bei 0
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "falsch-falsch"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "drei-worte-merken"}).status_code == 200


def test_change_password_requires_current_password(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "drei-worte-merken", "display_name": "Mia"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Falsches/fehlendes aktuelles Passwort -> 403
    assert client.post("/api/auth/change-password", headers=headers,
                       json={"current_password": "falsch-falsch", "new_password": "neues-passwort-1"}).status_code == 403
    assert client.post("/api/auth/change-password", headers=headers,
                       json={"new_password": "neues-passwort-1"}).status_code == 403

    # Korrekt -> Login nur noch mit dem neuen Passwort moeglich
    ok = client.post("/api/auth/change-password", headers=headers,
                     json={"current_password": "drei-worte-merken", "new_password": "neues-passwort-1"})
    assert ok.status_code == 200, ok.text
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "drei-worte-merken"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "neues-passwort-1"}).status_code == 200


def test_change_password_via_email_link_needs_no_current(client):
    """Passwort-vergessen-Flow: Login kam per Mail-Link (via=email) ->
    neues Passwort ohne altes setzbar."""
    r = client.post(
        "/api/auth/register",
        json={"email": "mia@test.ch", "password": "vergessenes-passwort", "display_name": "Mia"},
    )
    user_id = r.json()["user"]["id"]
    email_token = create_access_token(user_id, "student", via="email")
    headers = {"Authorization": f"Bearer {email_token}"}

    ok = client.post("/api/auth/change-password", headers=headers,
                     json={"new_password": "frisch-gesetzt-99"})
    assert ok.status_code == 200, ok.text
    assert client.post("/api/auth/login", json={"email": "mia@test.ch", "password": "frisch-gesetzt-99"}).status_code == 200


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
