"""Feedback: senden (alle Eingeloggten), lesen (nur Admin), Speicherung."""
from .test_library import make_admin, register_pw


def test_student_can_send_feedback(client):
    headers = register_pw(client, "mia@test.ch")
    r = client.post("/api/feedback", headers=headers,
                    json={"text": "Der Stift funktioniert super!", "page": "/app/lernen"})
    assert r.status_code == 201, r.text


def test_only_admin_can_read_feedback(client):
    headers = register_pw(client, "mia@test.ch")
    client.post("/api/feedback", headers=headers, json={"text": "Bitte mehr Geometrie-Aufgaben."})

    # Schueler darf die Liste NICHT lesen
    assert client.get("/api/feedback", headers=headers).status_code == 403

    # Admin sieht das gespeicherte Feedback inkl. Absender
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    r = client.get("/api/feedback", headers=admin)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["text"] == "Bitte mehr Geometrie-Aufgaben."
    assert items[0]["display_name"] == "mia"


def test_feedback_requires_login_and_length_limits(client):
    assert client.post("/api/feedback", json={"text": "hallo welt"}).status_code == 401
    headers = register_pw(client, "mia@test.ch")
    assert client.post("/api/feedback", headers=headers, json={"text": "ab"}).status_code == 422
    assert client.post("/api/feedback", headers=headers, json={"text": "x" * 2001}).status_code == 422
