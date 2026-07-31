"""Regressionstests fuer die Launch-Audit-Fixes."""
from app.services.sympy_verifier import extract_expression, verify
from app.services.tutor import advance_ladder, detect_intent
from app.services.sympy_verifier import Verification

from .conftest import register


# --- Fix: Aufgabe nur als Text -> pruefbaren Ausdruck ableiten ---
def test_extract_expression_from_prose():
    assert extract_expression("Löse 3x = 15") == "3x = 15"
    assert extract_expression("Berechne x: 2x + 4 = 10") == "2x + 4 = 10"
    assert extract_expression("Kein Gleichheitszeichen hier") is None


def test_textonly_exercise_is_solvable(client):
    h = register(client, "textonly@test.ch")
    ex = client.post("/api/exercises", json={"text": "Löse 3x = 15"}, headers=h)
    assert ex.status_code == 201
    assert ex.json()["math_expression"] == "3x = 15"
    aid = client.post(f"/api/exercises/{ex.json()['id']}/attempts", headers=h).json()["attempt"]["id"]
    # zwei echte Versuche, dann Loesung
    for msg in ("x = 4", "x = 6"):
        client.post(f"/api/attempts/{aid}/chat", json={"text": msg}, headers=h).read()
    client.post(f"/api/attempts/{aid}/chat", json={"text": "x = 5"}, headers=h).read()
    st = client.get(f"/api/attempts/{aid}", headers=h).json()
    assert st["attempt"]["solved"] is True


# --- Fix: Aufgabe abtippen zaehlt NICHT als eigener Umformungsschritt ---
def test_restating_exercise_is_not_a_step():
    assert verify("3x + 5 = 20", "3x + 5 = 20").status == "unknown"
    assert verify("3x + 5 = 20", "20 = 3x + 5").status == "unknown"
    # echte Umformung bleibt partial
    assert verify("3x + 5 = 20", "3x = 15").status == "partial"


# --- Fix: erweiterte Bettel-Erkennung ---
def test_more_plea_phrases_detected():
    v_unknown = Verification("unknown", "")
    for phrase in ("zeig mir die lösung", "wie lautet die antwort", "nenn mir das ergebnis",
                   "sag mir die antwort", "gib mir das resultat"):
        assert detect_intent(phrase, v_unknown) == "plea", phrase
    # Betteln erhoeht die Stufe nicht
    step = advance_ladder(2, 0, "plea")
    assert step.allowed_stage == 2 and step.own_attempts == 0


# --- Fix: PATCH /me mit explizitem null crasht nicht ---
def test_patch_me_with_null_is_safe(client):
    h = register(client, "patchnull@test.ch", name="Original")
    r = client.patch("/api/auth/me", json={"display_name": None, "grade_level": "8. Klasse"}, headers=h)
    assert r.status_code == 200
    assert r.json()["display_name"] == "Original"   # NOT-NULL blieb erhalten
    assert r.json()["grade_level"] == "8. Klasse"


# --- Fix: Eltern-Redeem respektiert den Freigabe-Schalter ---
def test_redeem_respects_share_flag(client):
    hs = register(client, "kind@test.ch", name="Kind")
    # eine geloeste Aufgabe erzeugen
    ex = client.post("/api/exercises", json={"text": "Löse 2x = 8"}, headers=hs)
    aid = client.post(f"/api/exercises/{ex.json()['id']}/attempts", headers=hs).json()["attempt"]["id"]
    for msg in ("x = 1", "x = 2", "x = 4"):
        client.post(f"/api/attempts/{aid}/chat", json={"text": msg}, headers=hs).read()
    code = client.get("/api/parents/invite", headers=hs).json()["invite_code"]

    hp = register(client, "mutter@test.ch", role="parent", name="Mutter")
    shared = client.post("/api/parents/redeem", json={"invite_code": code}, headers=hp).json()
    assert shared["solved_count"] >= 1  # mit Freigabe sichtbar

    client.patch("/api/auth/me", json={"share_with_parents": False}, headers=hs)
    hidden = client.post("/api/parents/redeem", json={"invite_code": code}, headers=hp).json()
    assert hidden["solved_count"] == 0           # ohne Freigabe genullt
    assert hidden["daily_activity"] == [0] * 7


def test_browser_fehler_landet_im_stoerungsprotokoll(client):
    """POST /api/feedback/app-fehler legt eine Alert-Zeile kind='client' an;
    dieselbe Meldung wird innerhalb der Drossel-Zeit nur einmal erfasst."""
    from app.database import SessionLocal
    from app.models import Alert
    from app.services import alert as alert_service
    from .test_library import register_pw

    alert_service._last_sent.clear()
    headers = register_pw(client, "jsfehler@test.ch")

    for _ in range(2):  # zweite identische Meldung wird gedrosselt
        r = client.post("/api/feedback/app-fehler", headers=headers,
                        json={"message": "TypeError: x is not a function", "url": "/app/lernen"})
        assert r.status_code == 201

    with SessionLocal() as db:
        rows = [a for a in db.query(Alert).all() if a.kind == "client"]
    assert len(rows) == 1
    assert "TypeError" in rows[0].detail and "/app/lernen" in rows[0].detail


def test_server_fehler_landet_im_stoerungsprotokoll(client):
    """Unbehandelte Exceptions -> 500 mit freundlicher Meldung + Alert kind='server'."""
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.main import app
    from app.models import Alert
    from app.services import alert as alert_service

    alert_service._last_sent.clear()

    @app.get("/api/_test_boom")
    def _boom():
        raise RuntimeError("kaputt")

    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/_test_boom")
            assert r.status_code == 500
            assert "Unerwarteter Fehler" in r.json()["detail"]
            r_en = c.get("/api/_test_boom", headers={"X-Lang": "en"})
            assert "Unexpected error" in r_en.json()["detail"]
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/api/_test_boom"]

    with SessionLocal() as db:
        rows = [a for a in db.query(Alert).all() if a.kind == "server"]
    assert rows and "RuntimeError" in rows[0].detail
