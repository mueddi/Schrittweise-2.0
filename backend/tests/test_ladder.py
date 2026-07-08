"""Hinweis-Leiter: Zustandsmaschine (Unit) + Einfrieren nach Loesung (HTTP)."""
from app.services.tutor import advance_ladder

from .conftest import register


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
