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


def test_problem_melden_haengt_den_zusammenhang_an(client):
    """Der Knopf im Chat: das Kind waehlt nur die Kategorie. Aufgabe, letzte
    Nachrichten und Bild holt der Server – «hat nicht funktioniert» ohne
    Zusammenhang waere fuer den Betreiber wertlos."""
    from app.database import SessionLocal
    from app.models import Message, MessageRole

    mia = register_pw(client, "mia@test.ch")
    ex = client.post("/api/exercises", headers=mia,
                     json={"text": "Löse nach x auf: 3x + 5 = 20", "image_path": "/api/exercises/images/abc"}).json()
    st = client.post(f"/api/exercises/{ex['id']}/attempts", headers=mia).json()
    aid = st["attempt"]["id"]
    with SessionLocal() as db:
        db.add(Message(attempt_id=aid, role=MessageRole.student, text="x = 7"))
        db.add(Message(attempt_id=aid, role=MessageRole.tutor, text="Fast – schau nochmal auf die 5."))
        db.commit()

    r = client.post("/api/feedback", headers=mia,
                    json={"kind": "problem", "category": "antwort", "text": "", "page": "/app/lernen",
                          "attempt_id": aid})
    assert r.status_code == 201, r.text

    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    offen = client.get("/api/feedback?kind=problem&offen=true", headers=admin).json()
    assert len(offen) == 1
    m = offen[0]
    assert m["category"] == "antwort" and m["attempt_id"] == aid
    assert m["image_path"] == "/api/exercises/images/abc"      # vom Versuch geerbt
    assert "AUFGABE: Löse nach x auf: 3x + 5 = 20" in m["context"]
    assert "LETZTE NACHRICHT DES KINDES: x = 7" in m["context"]
    assert "LETZTE TUTOR-ANTWORT: Fast" in m["context"]
    assert m["resolved_at"] is None

    # Erledigt markieren -> aus der offenen Liste raus, in der Gesamtliste noch da
    assert client.patch(f"/api/feedback/{m['id']}/erledigt", headers=admin).status_code == 200
    assert client.get("/api/feedback?kind=problem&offen=true", headers=admin).json() == []
    assert len(client.get("/api/feedback?kind=problem", headers=admin).json()) == 1
    assert client.patch(f"/api/feedback/{m['id']}/erledigt", headers=mia).status_code == 403


def test_problem_melden_nur_zu_eigenen_versuchen_und_mit_kategorie(client):
    mia = register_pw(client, "mia@test.ch")
    leo = register_pw(client, "leo@test.ch")
    ex = client.post("/api/exercises", headers=mia, json={"text": "2x = 10"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=mia).json()["attempt"]["id"]
    # fremder Versuch
    assert client.post("/api/feedback", headers=leo,
                       json={"kind": "problem", "category": "antwort", "attempt_id": aid}).status_code == 404
    # unbekannte Kategorie
    assert client.post("/api/feedback", headers=mia,
                       json={"kind": "problem", "category": "xyz", "attempt_id": aid}).status_code == 400
    # Foto-Erkennung vor dem Start: kein Versuch, aber Bild und erkannter Text
    r = client.post("/api/feedback", headers=mia,
                    json={"kind": "problem", "category": "erkennung", "image_path": "/api/exercises/images/xyz",
                          "context": "Fg=", "page": "/app/lernen"})
    assert r.status_code == 201
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    m = client.get("/api/feedback?kind=problem", headers=admin).json()[0]
    assert m["image_path"] == "/api/exercises/images/xyz" and "ERKANNTER TEXT: Fg=" in m["context"]
    # freies Feedback braucht weiterhin Text
    assert client.post("/api/feedback", headers=mia, json={"text": "ab"}).status_code == 422


def test_harmlose_browser_warnungen_loesen_keinen_alarm_aus(client):
    """3 von 5 Alarmen der letzten 14 Tage waren die «ResizeObserver loop»-
    Warnung, die jeder Browser beim Groesse-Aendern wirft. Eine verrauschte
    Fehlerseite schaut irgendwann niemand mehr an."""
    from app.routers.feedback import _harmlos

    assert _harmlos("ResizeObserver loop completed with undelivered notifications.")
    assert _harmlos("ResizeObserver loop limit exceeded")
    assert _harmlos("Script error.")
    # echte Fehler muessen weiterhin durch
    assert not _harmlos("TypeError: Cannot read properties of undefined")
    assert not _harmlos("Uncaught ReferenceError: api is not defined")
