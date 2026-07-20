"""Hinweis-Leiter: Zustandsmaschine (Unit) + Einfrieren nach Loesung (HTTP)."""
from app.services.sympy_verifier import Verification
from app.services.tutor import advance_ladder, detect_intent

from .conftest import register

_UNKNOWN = Verification("unknown", "test")


# ---------- Unit: Zustandsmaschine ----------
def test_plea_does_not_advance_or_count():
    step = advance_ladder(current_stage=1, own_attempts=0, intent="plea")
    assert step.allowed_stage == 1
    assert step.own_attempts == 0
    assert not step.permit_solution


def test_stuck_advances_one_rung():
    assert advance_ladder(0, 0, "stuck").allowed_stage == 1
    assert advance_ladder(1, 0, "stuck").allowed_stage == 2
    assert advance_ladder(2, 0, "stuck").allowed_stage == 3


def test_full_solution_locked_until_two_attempts():
    # Stufe 3, erst 1 Versuch -> Stufe 4 gesperrt, bleibt auf 3
    step = advance_ladder(3, 0, "attempt")
    assert step.own_attempts == 1
    assert step.allowed_stage == 3
    assert not step.permit_solution
    # zweiter Versuch -> Stufe 4 frei
    step = advance_ladder(3, 1, "attempt")
    assert step.own_attempts == 2
    assert step.allowed_stage == 4
    assert step.permit_solution


def test_correct_step_does_not_raise_stage():
    """Ein RICHTIGER eigener Schritt (partial) darf die Hilfe-Stufe nicht
    hochtreiben – mehr Hilfe gibt es nur bei Fehlern oder auf Anfrage."""
    assert detect_intent("3x = 15", Verification("partial", "test", extracted="3x = 15")) == "step"
    step = advance_ladder(1, 0, "step")
    assert step.allowed_stage == 1  # Stufe bleibt
    assert step.own_attempts == 1  # zaehlt aber als echter Versuch
    assert not step.permit_solution


def test_unverifiable_attempt_does_not_raise_stage():
    assert detect_intent("42", Verification("unknown", "test", extracted="42")) == "step"


def test_wrong_attempt_still_raises_stage():
    assert detect_intent("x = 99", Verification("incorrect", "test", extracted="x = 99")) == "attempt"
    step = advance_ladder(1, 0, "attempt")
    assert step.allowed_stage == 2  # Fehler -> mehr Hilfe erlaubt
    assert step.own_attempts == 1


def test_simpler_keeps_stage():
    """«Verstehe es nicht» / «erklaer einfacher» = gleiche Stufe, einfacher erklaert
    – die Leiter darf dadurch NICHT hochklettern."""
    assert detect_intent("Ich verstehe es nicht.", _UNKNOWN) == "simpler"
    assert detect_intent("Kannst du es mir einfacher erklären?", _UNKNOWN) == "simpler"
    assert detect_intent("das kapier ich nicht", _UNKNOWN) == "simpler"
    step = advance_ladder(2, 1, "simpler")
    assert step.allowed_stage == 2
    assert step.own_attempts == 1
    assert not step.permit_solution


def test_tip_requests_still_advance():
    assert detect_intent("Gib mir bitte einen Tipp.", _UNKNOWN) == "stuck"
    assert detect_intent("Zeig mir bitte den ersten Schritt.", _UNKNOWN) == "stuck"


def test_plea_unlocks_solution_after_earned_attempts():
    """Nach 2 echten Versuchen auf Stufe 3 ist die Loesung auf Nachfrage frei."""
    step = advance_ladder(3, 2, "plea")
    assert step.allowed_stage == 4
    assert step.permit_solution
    assert step.own_attempts == 2  # Nachfragen zaehlt nicht als Versuch


def test_plea_stays_locked_without_enough_attempts():
    # Stufe 3, aber erst 1 Versuch -> weiterhin gesperrt
    step = advance_ladder(3, 1, "plea")
    assert step.allowed_stage == 3
    assert not step.permit_solution
    # genug Versuche, aber Stufe noch tief -> weiterhin gesperrt
    step = advance_ladder(1, 2, "plea")
    assert step.allowed_stage == 1
    assert not step.permit_solution


def test_correct_marks_solved():
    step = advance_ladder(2, 1, "correct")
    assert step.solved
    assert step.own_attempts == 1  # korrekt zaehlt nicht als weiterer Versuch


# ---------- HTTP: geloester Attempt friert ein ----------
def _chat(client, headers, attempt_id, text):
    with client.stream("POST", f"/api/attempts/{attempt_id}/chat", headers=headers, json={"text": text}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    return client.get(f"/api/attempts/{attempt_id}", headers=headers).json()["attempt"]


def test_tutor_messages_carry_hint_level(client):
    """Tutor-Antworten tragen ihre Hilfe-Stufe (fuer das Stufen-Tag im Chat)."""
    h = register(client, "stufen@test.ch", name="Stufen")
    ex = client.post("/api/exercises", headers=h,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=h).json()["attempt"]["id"]

    _chat(client, h, aid, "keine ahnung wie anfangen")
    msgs = client.get(f"/api/attempts/{aid}", headers=h).json()["messages"]
    tutor_msgs = [m for m in msgs if m["role"] == "tutor"]
    assert tutor_msgs[0]["hint_level"] is None  # Eroeffnung hat keine Stufe
    assert tutor_msgs[-1]["hint_level"] == 1  # erste Hilfe = Stufe 1


def test_solved_attempt_state_frozen(client):
    h = register(client, "loeser@test.ch", name="Loeser")
    ex = client.post("/api/exercises", headers=h,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=h).json()["attempt"]["id"]

    a = _chat(client, h, aid, "x = 5")
    assert a["solved"] is True
    frozen_level, frozen_attempts = a["hint_level"], a["own_attempts"]

    # weitere Nachrichten aendern Stufe/Versuche nicht mehr
    a = _chat(client, h, aid, "warum ist das so?")
    assert a["hint_level"] == frozen_level
    assert a["own_attempts"] == frozen_attempts
    a = _chat(client, h, aid, "x = 7")
    assert a["hint_level"] == frozen_level
    assert a["own_attempts"] == frozen_attempts
    assert a["solved"] is True


def test_rechenaufgabe_wird_geloest_markiert(client):
    """«2 + 4» + Antwort «= 6» -> Attempt ist geloest (gruener Haken/🎉)."""
    from .test_library import register_pw

    headers = register_pw(client, "rechnen@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "2 + 4"}).json()
    assert ex["math_expression"] == "2 + 4"
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]

    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "= 6"}) as r:
        assert r.status_code == 200
        assert "".join(r.iter_text())

    state = client.get(f"/api/attempts/{aid}", headers=headers).json()
    assert state["attempt"]["solved"] is True
    student = [m for m in state["messages"] if m["role"] == "student"][-1]
    assert student["verification_status"] == "correct"
