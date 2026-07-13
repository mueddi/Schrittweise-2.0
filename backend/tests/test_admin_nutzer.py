"""Admin-Nutzerverwaltung: Liste, Suche, Token-Gutschrift mit Protokoll."""
from app.database import SessionLocal
from app.models import TokenAdjustment, User

from .test_library import make_admin, register_pw


def _setup(client):
    student = register_pw(client, "mia@test.ch")
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    return student, admin


def test_nutzerliste_nur_fuer_admin(client):
    student, admin = _setup(client)
    assert client.get("/api/admin/nutzer", headers=student).status_code == 403
    r = client.get("/api/admin/nutzer", headers=admin)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert {"mia@test.ch", "chef@test.ch"} <= emails

    # Suche filtert
    r = client.get("/api/admin/nutzer?q=mia", headers=admin)
    assert [u["email"] for u in r.json()] == ["mia@test.ch"]


def test_token_gutschrift_und_abzug(client):
    student, admin = _setup(client)
    with SessionLocal() as db:
        uid = db.query(User).filter(User.email == "mia@test.ch").one().id

    # Gutschrift
    r = client.post(f"/api/admin/nutzer/{uid}/tokens", headers=admin,
                    json={"tokens": 200, "grund": "Webhook verpasst"})
    assert r.status_code == 200
    assert r.json()["token_balance"] == 200

    # Abzug unter 0 wird bei 0 gedeckelt
    r = client.post(f"/api/admin/nutzer/{uid}/tokens", headers=admin,
                    json={"tokens": -500, "grund": "Rueckerstattung"})
    assert r.json()["token_balance"] == 0

    # Beide Buchungen protokolliert
    with SessionLocal() as db:
        rows = db.query(TokenAdjustment).order_by(TokenAdjustment.id).all()
        assert [a.tokens for a in rows] == [200, -500]
        assert rows[0].reason == "Webhook verpasst"
        assert rows[0].admin_id is not None


def test_token_buchung_validierung(client):
    student, admin = _setup(client)
    with SessionLocal() as db:
        uid = db.query(User).filter(User.email == "mia@test.ch").one().id
    # 0 Tokens und fehlender Grund sind ungueltig; Schueler duerfen gar nicht
    assert client.post(f"/api/admin/nutzer/{uid}/tokens", headers=admin,
                       json={"tokens": 0, "grund": "nix"}).status_code == 422
    assert client.post(f"/api/admin/nutzer/{uid}/tokens", headers=admin,
                       json={"tokens": 10, "grund": ""}).status_code == 422
    assert client.post(f"/api/admin/nutzer/{uid}/tokens", headers=student,
                       json={"tokens": 10, "grund": "hack"}).status_code == 403
    assert client.post("/api/admin/nutzer/999999/tokens", headers=admin,
                       json={"tokens": 10, "grund": "test"}).status_code == 404
