"""Konto-Löschung: Selbstbedienung mit Passwort, kaskadierte Datenlöschung."""
from app.database import SessionLocal
from app.models import ApiUsage, Attempt, Exercise, Message, Topic, User

from .test_library import make_admin, register_pw


def _setup_student_with_data(client):
    headers = register_pw(client, "mia@test.ch")
    topic = client.post("/api/topics", headers=headers, json={"name": "Algebra"}).json()
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20", "topic_id": topic["id"]}).json()
    client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers)
    return headers


def test_delete_requires_correct_password(client):
    headers = _setup_student_with_data(client)
    r = client.post("/api/auth/delete-account", headers=headers, json={"password": "falsch-falsch"})
    assert r.status_code == 403
    # Konto besteht weiter
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_delete_removes_all_user_data(client):
    headers = _setup_student_with_data(client)
    r = client.post("/api/auth/delete-account", headers=headers,
                    json={"password": "test-passwort-123"})
    assert r.status_code == 204

    # Token ist tot, Daten sind weg
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    with SessionLocal() as db:
        assert db.query(User).count() == 0
        assert db.query(Exercise).count() == 0
        assert db.query(Attempt).count() == 0
        assert db.query(Message).count() == 0
        assert db.query(Topic).count() == 0

    # E-Mail ist wieder frei fuer eine Neuregistrierung
    assert client.post("/api/auth/register",
                       json={"terms_accepted": True, "email": "mia@test.ch",
                             "password": "neues-passwort-123"}).status_code == 200


def test_delete_anonymizes_usage_rows(client):
    headers = _setup_student_with_data(client)
    with SessionLocal() as db:
        uid = db.query(User).filter(User.email == "mia@test.ch").one().id
        exid = db.query(Exercise).first().id
        db.add(ApiUsage(user_id=uid, exercise_id=exid, kind="chat",
                        model="claude-haiku-4-5", cost_usd=0.01, charged_tokens=3))
        db.commit()

    assert client.post("/api/auth/delete-account", headers=headers,
                       json={"password": "test-passwort-123"}).status_code == 204
    with SessionLocal() as db:
        row = db.query(ApiUsage).one()  # Statistik bleibt, Personenbezug weg
        assert row.user_id is None
        assert row.exercise_id is None


def test_admin_cannot_self_delete(client):
    headers = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    r = client.post("/api/auth/delete-account", headers=headers,
                    json={"password": "test-passwort-123"})
    assert r.status_code == 403
