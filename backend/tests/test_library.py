"""Aufgaben-Bibliothek: Betreiber pflegt Aufgaben, Schueler starten sie im Tutor."""
import types

from app.database import SessionLocal
from app.models import Attempt, Exercise, User


def make_admin(email: str) -> None:
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        u.is_admin = True
        db.commit()


def register_pw(client, email: str, password: str = "test-passwort-123") -> dict:
    r = client.post(
        "/api/auth/register",
        json={"terms_accepted": True, "email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def tiny_png() -> bytes:
    """Kleinstes gueltiges PNG – fuer Foto-/Zeichnungs-Tests (test_images)."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, format="PNG")
    return buf.getvalue()


def ensure_topic(client, headers, name):
    r = client.post("/api/library/topics", headers=headers, json={"name": name})
    assert r.status_code in (201, 409, 403), r.text
    return r


def anlegen(client, headers, text="Löse nach x auf: 3x + 5 = 20", expr=None, category="Gleichungen",
            grades=("oberstufe",), difficulty="leicht", source="eigene"):
    ensure_topic(client, headers, category)
    return client.post("/api/library", headers=headers,
                       json={"text": text, "math_expression": expr, "category": category,
                             "grade_levels": list(grades), "difficulty": difficulty, "source": source})


def _admin(client):
    headers = register_pw(client, "admin@test.ch")
    make_admin("admin@test.ch")
    return headers


def test_admin_routes_forbidden_for_students(client):
    headers = register_pw(client, "schueler@test.ch")
    assert anlegen(client, headers).status_code == 403
    assert client.delete("/api/library/1", headers=headers).status_code == 403
    assert client.post("/api/library/generieren", headers=headers,
                       json={"category": "x", "lernziel": "Brueche kuerzen"}).status_code == 403
    assert client.get("/api/library").status_code == 401     # Lesen ohne Login


def test_anlegen_listen_filtern(client):
    admin = _admin(client)
    r = anlegen(client, admin)
    assert r.status_code == 201, r.text
    a = r.json()
    # Pruefausdruck wird aus dem Text gezogen, wenn keiner angegeben ist
    assert a["math_expression"] and "3" in a["math_expression"]
    assert a["grade_levels"] == ["oberstufe"] and a["status"] == "neu"

    anlegen(client, admin, text="Wie viel sind 25 % von 240 Franken?", category="Prozente",
            grades=("mittelstufe", "oberstufe"), difficulty="mittel")
    anlegen(client, admin, text="Leite f(x) = x^3 - 4x^2 ab", category="Analysis",
            grades=("gymnasium",), difficulty="schwer")

    student = register_pw(client, "mia@test.ch")
    assert len(client.get("/api/library", headers=student).json()) == 3
    assert [e["category"] for e in client.get("/api/library?category=Prozente", headers=student).json()] == ["Prozente"]
    mittel = client.get("/api/library?grade=mittelstufe", headers=student).json()
    assert [e["category"] for e in mittel] == ["Prozente"]
    assert [e["category"] for e in client.get("/api/library?difficulty=schwer", headers=student).json()] == ["Analysis"]
    assert [e["category"] for e in client.get("/api/library?q=franken", headers=student).json()] == ["Prozente"]


def test_validierung(client):
    admin = _admin(client)
    assert anlegen(client, admin, grades=("5. Klasse",)).status_code == 400
    assert anlegen(client, admin, difficulty="unmoeglich").status_code == 400
    # unbekanntes Thema
    r = client.post("/api/library", headers=admin,
                    json={"text": "x", "category": "GibtEsNicht", "grade_levels": ["oberstufe"]})
    assert r.status_code == 400
    # Pruefausdruck, den SymPy nicht aufloesen kann, wird abgelehnt statt still gespeichert
    r = anlegen(client, admin, text="Zeichne ein Dreieck", expr="zeichne(dreieck)")
    assert r.status_code == 400
    # ohne Ausdruck bleibt eine nicht pruefbare Aufgabe erlaubt
    r = anlegen(client, admin, text="Zeichne ein rechtwinkliges Dreieck mit a = 3 cm und b = 4 cm")
    assert r.status_code == 201 and r.json()["math_expression"] is None


def test_schueler_startet_aufgabe_im_tutor(client):
    """Der Sinn der Bibliothek: ein Klick, und die Aufgabe ist im Chat."""
    admin = _admin(client)
    a = anlegen(client, admin).json()
    student = register_pw(client, "mia@test.ch")

    r = client.post(f"/api/library/{a['id']}/start", headers=student)
    assert r.status_code == 201, r.text
    st = r.json()
    assert st["exercise"]["text"] == a["text"]
    assert st["exercise"]["math_expression"] == a["math_expression"]
    assert st["messages"][0]["role"] == "tutor"        # Eroeffnung steht schon da
    attempt_id = st["attempt"]["id"]

    # Ein zweiter Start legt KEINE zweite Kopie an, nur einen neuen Versuch
    st2 = client.post(f"/api/library/{a['id']}/start", headers=student).json()
    assert st2["exercise"]["id"] == st["exercise"]["id"]
    with SessionLocal() as db:
        kopien = db.query(Exercise).filter(Exercise.library_id == a["id"]).all()
        assert len(kopien) == 1 and kopien[0].text == a["text"]
        assert db.query(Attempt).filter(Attempt.exercise_id == kopien[0].id).count() == 2

    # Stand in der Liste: offen mit juengstem Versuch; nach dem Loesen «geloest»
    liste = client.get("/api/library", headers=student).json()
    assert liste[0]["status"] == "offen" and liste[0]["attempt_id"] == st2["attempt"]["id"]
    with SessionLocal() as db:
        db.get(Attempt, attempt_id).solved = True
        db.commit()
    assert client.get("/api/library", headers=student).json()[0]["status"] == "geloest"
    # Ein anderer Schueler sieht seinen eigenen Stand, nicht Mias
    leo = register_pw(client, "leo@test.ch")
    assert client.get("/api/library", headers=leo).json()[0]["status"] == "neu"

    assert client.post("/api/library/999/start", headers=student).status_code == 404


def test_bearbeiten_und_loeschen(client):
    admin = _admin(client)
    a = anlegen(client, admin).json()
    ensure_topic(client, admin, "Terme")
    r = client.patch(f"/api/library/{a['id']}", headers=admin,
                     json={"text": "Löse: 2x = 10", "category": "Terme", "difficulty": "schwer",
                           "grade_levels": ["gymnasium", "oberstufe"], "source": "Serlo, CC BY-SA 4.0"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["category"] == "Terme" and b["difficulty"] == "schwer"
    assert b["grade_levels"] == ["oberstufe", "gymnasium"]       # feste Reihenfolge
    assert "2" in b["math_expression"] and "10" in b["math_expression"]  # Ausdruck folgt dem neuen Text
    assert b["source"] == "Serlo, CC BY-SA 4.0"

    assert client.delete(f"/api/library/{a['id']}", headers=admin).status_code == 204
    assert client.get("/api/library", headers=admin).json() == []
    assert client.delete(f"/api/library/{a['id']}", headers=admin).status_code == 404


def test_import_alles_oder_nichts(client):
    admin = _admin(client)
    ensure_topic(client, admin, "Brüche")
    eintrag = {"category": "Brüche", "grade_levels": ["oberstufe"], "difficulty": "leicht", "source": "eigene"}
    r = client.post("/api/library/import", headers=admin, json={"aufgaben": [
        {"text": "Berechne 1/2 + 1/4", **eintrag},
        {"text": "Kürze 12/18", **eintrag},
    ]})
    assert r.status_code == 201, r.text
    assert len(r.json()) == 2
    # Eine kaputte Zeile -> nichts gespeichert, Fehler nennt die Zeile
    r = client.post("/api/library/import", headers=admin, json={"aufgaben": [
        {"text": "Berechne 3/4 - 1/8", **eintrag},
        {"text": "x", **{**eintrag, "grade_levels": ["ungueltig"]}},
    ]})
    assert r.status_code == 400 and "Aufgabe 2" in r.json()["detail"]
    assert len(client.get("/api/library", headers=admin).json()) == 2


def test_ki_erzeugung_ist_vorschau_und_kostet_den_betreiber(client, monkeypatch):
    from app.config import settings
    from app.models import ApiUsage
    from app.routers import library as library_router

    admin = _admin(client)
    ensure_topic(client, admin, "Prozente")
    antwort = ('[{"frage": "Ein Velo kostet 240 Franken, 25 % Rabatt. Wie viel sparst du?", "ausdruck": "240 * 0.25"},'
               ' {"frage": "Zeichne einen Prozentbalken für 35 %.", "ausdruck": ""}]')
    usage = types.SimpleNamespace(input_tokens=300, output_tokens=120,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0)
    calls = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=antwort)], usage=usage)

    class _Client:
        def __init__(self, api_key, **kwargs):
            self.messages = _Messages()

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(library_router, "anthropic", types.SimpleNamespace(Anthropic=_Client), raising=False)
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Client))

    r = client.post("/api/library/generieren", headers=admin,
                    json={"category": "Prozente", "grade_level": "Gymnasium 1./2.", "difficulty": "mittel",
                          "lernziel": "Rabatt in Franken berechnen", "anzahl": 2})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["aufgaben"]) == 2
    assert data["aufgaben"][0]["math_expression"]                 # nachgerechnet und behalten
    assert data["aufgaben"][1]["math_expression"] is None         # Zeichnen: nicht pruefbar
    assert data["aufgaben"][0]["grade_levels"] == ["gymnasium"]  # Alt-Wert normalisiert
    assert data["aufgaben"][0]["source"] == "KI-erzeugt"
    assert data["kosten_rappen"] > 0
    assert "Gymnasium" in calls[0]["messages"][0]["content"] and "Rabatt" in calls[0]["messages"][0]["content"]

    # Nur Vorschau: nichts gespeichert, aber der Aufruf ist erfasst
    assert client.get("/api/library", headers=admin).json() == []
    with SessionLocal() as db:
        zeile = db.query(ApiUsage).filter(ApiUsage.kind == "generiert").one()
        assert zeile.charged_tokens == 0     # Betreiber zahlt, kein Schueler

    # Uebernehmen laeuft ueber den Import
    r = client.post("/api/library/import", headers=admin, json={"aufgaben": data["aufgaben"]})
    assert r.status_code == 201 and len(r.json()) == 2


def test_topic_management(client):
    admin = _admin(client)
    student = register_pw(client, "mia@test.ch")

    assert client.post("/api/library/topics", headers=student, json={"name": "X"}).status_code == 403
    r = client.post("/api/library/topics", headers=admin, json={"name": "Prozentrechnen"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert client.post("/api/library/topics", headers=admin, json={"name": "prozentrechnen"}).status_code == 409

    a = anlegen(client, admin, text="Rabatt: 20 % von 50 Franken", category="Prozentrechnen").json()
    r = client.patch(f"/api/library/topics/{tid}", headers=admin, json={"name": "Prozente & Zins"})
    assert r.status_code == 200 and r.json()["doc_count"] == 1
    liste = client.get("/api/library", headers=student).json()
    assert any(e["id"] == a["id"] and e["category"] == "Prozente & Zins" for e in liste)

    assert client.delete(f"/api/library/topics/{tid}", headers=admin).status_code == 409
    client.delete(f"/api/library/{a['id']}", headers=admin)
    assert client.delete(f"/api/library/topics/{tid}", headers=admin).status_code == 204
    names = [t["name"] for t in client.get("/api/library/topics", headers=student).json()]
    assert "Prozente & Zins" not in names


def test_klassen_schluessel():
    from app.routers.library import klassen_schluessel

    assert klassen_schluessel("Gymnasium 1./2.") == "gymnasium"
    assert klassen_schluessel("mittelstufe") == "mittelstufe"
    assert klassen_schluessel("2. Oberstufe") == "oberstufe"
    assert klassen_schluessel(None) == "oberstufe"
