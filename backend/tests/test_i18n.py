"""Zweisprachigkeit (de/en) + Stufen-Logik (mittelstufe/oberstufe/gymnasium)."""
from .test_library import register_pw


def _mit_sprache(client, email, lang):
    headers = register_pw(client, email)
    r = client.patch("/api/auth/me", headers=headers, json={"language": lang})
    assert r.status_code == 200
    assert r.json()["language"] == lang
    return headers


def test_opener_und_mock_tutor_auf_englisch(client):
    headers = _mit_sprache(client, "en@test.ch", "en")

    ex = client.post("/api/exercises", headers=headers, json={"text": "3x + 5 = 20"}).json()
    state = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()
    opener = state["messages"][0]["text"]
    assert "Let's go" in opener
    assert "Los geht" not in opener

    aid = state["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "no idea"}) as r:
        assert r.status_code == 200
        reply = "".join(r.iter_text())
    assert "No stress" in reply  # englischer Mock-Tutor


def test_fehlermeldungen_auf_englisch(client):
    headers = _mit_sprache(client, "en2@test.ch", "en")
    # 404 einer fremden Session in Nutzersprache
    r = client.get("/api/attempts/999999", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Session not found"

    # Login-Fehler vor dem Einloggen: Sprache kommt aus dem X-Lang-Header
    r = client.post("/api/auth/login", headers={"X-Lang": "en"},
                    json={"email": "gibtsnicht@test.ch", "password": "falschfalsch"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Email or password is incorrect."


def test_deutsch_bleibt_standard(client):
    headers = register_pw(client, "de@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x + 5 = 20"}).json()
    opener = client.post(f"/api/exercises/{ex['id']}/attempts",
                         headers=headers).json()["messages"][0]["text"]
    assert "Los geht's" in opener


def test_meta_bitte_erzeugt_echte_aufgabe(client):
    """«Mache mir eine Aufgabe» wird nicht woertlich gespeichert, sondern
    durch eine erzeugte Aufgabe ersetzt (Mock-Fallback ohne API-Key)."""
    headers = register_pw(client, "meta@test.ch")

    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "mache mir eine aufgabe"}).json()
    assert "mache mir" not in ex["text"].lower()
    assert ex["text"]  # echte Aufgabe vorhanden
    opener = client.post(f"/api/exercises/{ex['id']}/attempts",
                         headers=headers).json()["messages"][0]["text"]
    assert "mache mir" not in opener.lower()

    # englische Bitte funktioniert ebenso
    ex_en = client.post("/api/exercises", headers=headers,
                        json={"text": "make me a task please"}).json()
    assert "make me" not in ex_en["text"].lower()

    # echte Aufgaben bleiben unveraendert
    real = client.post("/api/exercises", headers=headers,
                       json={"text": "Löse nach x auf: 3x + 5 = 20"}).json()
    assert real["text"] == "Löse nach x auf: 3x + 5 = 20"


def test_generieren_endpoint_startet_aufgabe(client):
    """POST /api/exercises/generieren erzeugt Aufgabe + Attempt in einem
    Schritt; der Fallback richtet sich nach der Stufe."""
    headers = register_pw(client, "gen@test.ch")
    client.patch("/api/auth/me", headers=headers, json={"grade_level": "gymnasium"})

    r = client.post("/api/exercises/generieren", headers=headers, json={})
    assert r.status_code == 201, r.text
    state = r.json()
    assert state["attempt"]["id"]
    assert "f(x)" in state["exercise"]["text"]  # Gymnasium-Fallback

    client.patch("/api/auth/me", headers=headers, json={"grade_level": "mittelstufe"})
    r2 = client.post("/api/exercises/generieren", headers=headers, json={})
    assert r2.status_code == 201
    assert "348" in r2.json()["exercise"]["text"]  # Mittelstufe-Fallback


def test_regie_kennt_die_drei_stufen():
    from app.services.tutor import LadderStep, _regie
    from app.services.sympy_verifier import Verification

    v = Verification(status="unknown", detail="-", solution=None)
    step = LadderStep("question", 1, 0, False, False)

    gymi = _regie(step, v, "f(x) = x^2", None, "gymnasium")
    assert "Matura" in gymi
    mittel = _regie(step, v, "12 + 7", None, "mittelstufe")
    assert "Mittelstufe" in mittel and "einfache Sprache" in mittel
    ober = _regie(step, v, "3x + 5 = 20", None, "oberstufe")
    assert "Oberstufe" in ober
    # Legacy-Werte aus Alt-Konten funktionieren weiter
    legacy = _regie(step, v, "f(x) = x^2", None, "Gymnasium 1./2.")
    assert "Matura" in legacy


def test_regie_erzwingt_englisch_und_system_bleibt_cachebar():
    from app.services.tutor import LadderStep, _build_system, _regie
    from app.services.sympy_verifier import Verification

    v = Verification(status="unknown", detail="-", solution=None)
    step = LadderStep("question", 1, 0, False, False)
    en = _regie(step, v, "3x + 5 = 20", None, "oberstufe", "en")
    assert "Englisch" in en
    de = _regie(step, v, "3x + 5 = 20", None, "oberstufe", "de")
    assert "Englisch" not in de

    # System besteht nur noch aus dem statischen, gecachten Prompt-Block –
    # die Regie wandert in die letzte User-Nachricht (Cache-Praefix stabil).
    system = _build_system()
    assert len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_regie_traegt_loesung_als_orientierung():
    """Die verifizierte Loesung geht IMMER als interner Kontext mit –
    gesperrt markiert, solange Stufe 4 nicht freigegeben ist."""
    from app.services.tutor import LadderStep, _regie
    from app.services.sympy_verifier import Verification

    v = Verification(status="incorrect", detail="-", solution="x = 5")
    locked = _regie(LadderStep("wrong", 2, 1, False, False), v, "3x + 5 = 20", None)
    assert "x = 5" in locked and "NIEMALS nennen" in locked
    freigegeben = _regie(LadderStep("plea", 4, 2, False, True), v, "3x + 5 = 20", None)
    assert "jetzt zeigbar" in freigegeben and "x = 5" in freigegeben


def test_regie_landet_in_letzter_user_nachricht():
    from app.services.tutor import _history_to_messages

    history = [
        {"role": "tutor", "text": "Los geht's!"},
        {"role": "student", "text": "3x = 15"},
    ]
    msgs = _history_to_messages(history, image=(b"TASK", "image/jpeg"),
                                regie="REGIE-ANWEISUNG: ...")
    # Bild-Nachricht traegt den Cache-Breakpoint auf dem letzten Block
    assert msgs[0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    last = msgs[-1]
    assert last["role"] == "user"
    assert last["content"][0]["text"].startswith("REGIE-ANWEISUNG")
    assert last["content"][1]["text"] == "3x = 15"


def test_regie_warnt_bei_ungepruefter_antwort():
    from app.services.tutor import LadderStep, _regie
    from app.services.sympy_verifier import Verification

    step = LadderStep("question", 1, 0, False, False)
    unknown = _regie(step, Verification("unknown", "-", None), "2 + 4", None, "oberstufe")
    assert "NICHT automatisch geprueft" in unknown
    correct = _regie(step, Verification("correct", "-", None), "2 + 4", None, "oberstufe")
    assert "NICHT automatisch geprueft" not in correct
