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
    """Massgeblich sind die EIGENEN VERSUCHE, nicht die Hilfe-Stufe.

    Die frueher zusaetzlich verlangte Mindeststufe 3 ist bewusst weg: eigene
    Schritte erhoehen die Stufe absichtlich nicht, also blieb ein Kind, das
    brav selber rechnete, auf Stufe 1 – und wurde beim Nachfragen fuer immer
    abgewiesen. Die Zusage lautet «nach 2 eigenen Versuchen», nicht «nach
    genug Hilfe».
    """
    # Erst 1 Versuch -> weiterhin gesperrt
    step = advance_ladder(3, 1, "plea")
    assert step.allowed_stage == 3
    assert not step.permit_solution
    # gar kein Versuch, egal wie hoch die Stufe -> gesperrt
    step = advance_ladder(3, 0, "plea")
    assert not step.permit_solution
    # genug eigene Versuche -> freigegeben, auch auf tiefer Stufe
    step = advance_ladder(1, 2, "plea")
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


# --- Regressionen aus einem echten Verlauf (Attempt 41, 19 Nachrichten) ---

def test_loesung_erwaehnen_ist_kein_betteln():
    """«Ich verstehe die Lösung nicht» ist eine Bitte um Erklaerung.

    Vorher schnappte sich das blosse Wort «Loesung» die Nachricht und der
    Tutor lehnte ab, statt zu erklaeren – der Schueler fuehlte sich ignoriert.
    """
    assert detect_intent("Ich verstehe die Lösung nicht", _UNKNOWN) == "simpler"
    assert detect_intent("wie kommst du auf diese Lösung?", _UNKNOWN) != "plea"
    assert detect_intent("kannst du die Antwort nochmal erklären", _UNKNOWN) != "plea"
    # echtes Betteln bleibt Betteln
    assert detect_intent("Gib mir die Lösung", _UNKNOWN) == "plea"
    assert detect_intent("sag mir einfach die antwort", _UNKNOWN) == "plea"
    assert detect_intent("wie lautet das ergebnis", _UNKNOWN) == "plea"


def test_normales_reden_treibt_die_leiter_nicht_hoch():
    """Kommentare/Rueckfragen duerfen keine Hilfe-Stufe kosten."""
    for satz in ("erkläre mir die theorie", "ok", "du hast nicht fertig geschrieben",
                 "ich habe geteilt durch gemacht"):
        assert detect_intent(satz, _UNKNOWN) == "talk", satz
    vorher = 2
    step = advance_ladder(vorher, 0, "talk")
    assert step.allowed_stage == vorher
    assert step.own_attempts == 0


def test_leiter_friert_nicht_ein_aber_hilfe_bitten_zaehlen_nicht_als_versuch():
    """Echter Produktionsfall: 19 Nachrichten, Stufe 3, own_attempts = 0.

    Der erste Anlauf dagegen zaehlte eine Hilfe-Bitte ab Stufe 3 als eigenen
    Versuch – damit gaben fuenf Knopfdruecke («Tipp») die volle Loesung frei,
    ohne dass das Kind je gerechnet hatte. Die Zusage «erst nach 2 eigenen
    Versuchen» war ausgehoehlt. Das Einfrieren loest jetzt die plea-Regel:
    sie verlangt keine Mindeststufe mehr, aber echte eigene Versuche.
    """
    stage, attempts = 0, 0
    for _ in range(6):
        step = advance_ladder(stage, attempts, "stuck")
        stage, attempts = step.allowed_stage, step.own_attempts
    assert (stage, attempts) == (3, 0), "Nachfragen darf keine Versuche erfinden"
    assert advance_ladder(stage, attempts, "plea").permit_solution is False

    # Wer selbst rechnet, kommt an die Loesung – auch auf Stufe 1, denn
    # eigene Schritte erhoehen die Stufe absichtlich nicht.
    stage, attempts = 0, 0
    for _ in range(2):
        step = advance_ladder(stage, attempts, "step")
        stage, attempts = step.allowed_stage, step.own_attempts
    frei = advance_ladder(stage, attempts, "plea")
    assert frei.permit_solution is True and frei.allowed_stage == 4

    # Notausgang: langes Gespraech mit mindestens einem eigenen Versuch
    assert advance_ladder(3, 1, "plea", turns=12).permit_solution is True
    assert advance_ladder(3, 0, "plea", turns=30).permit_solution is False


def test_mundart_wird_verstanden():
    """Die App richtet sich an Schweizer Kinder. Die Muster kannten nur
    Hochdeutsch, also fiel JEDE Mundart-Nachricht in den "talk"-Zweig – und
    dort steht in der Regie ausdruecklich «das ist kein Hilferuf, keine neue
    Hilfe anbieten». Ein Kind, das Mundart schreibt, kam nie ueber Stufe 1."""
    assert detect_intent("nei ich verstahs nöd", _UNKNOWN) == "simpler"
    assert detect_intent("ich verstahne die lösig nöd", _UNKNOWN) == "simpler"
    assert detect_intent("chasch mir helfe", _UNKNOWN) == "stuck"
    assert detect_intent("ich weiss nöd wie", _UNKNOWN) == "stuck"
    assert detect_intent("wie gaht das", _UNKNOWN) == "stuck"
    assert detect_intent("ich cha das nid", _UNKNOWN) == "stuck"
    assert detect_intent("zeig mer d lösig", _UNKNOWN) == "plea"
    assert detect_intent("was isch d antwort", _UNKNOWN) == "plea"


def test_hoefliche_formen_werden_erkannt():
    """«zeige/sage» fielen an der Wortgrenze durch, «ich will die lösung» und
    «löse die aufgabe für mich» hatten gar kein Muster – alles wurde "talk"."""
    for msg in ["zeige mir die lösung", "sage mir die lösung", "ich will die lösung",
                "ich brauche die lösung", "löse die aufgabe für mich"]:
        assert detect_intent(msg, _UNKNOWN) == "plea", msg
    assert detect_intent("ich kann das nicht", _UNKNOWN) == "stuck"
    assert detect_intent("wie fange ich an", _UNKNOWN) == "stuck"


def test_verneinung_ist_kein_betteln():
    """«zeig mir NICHT die Lösung» loeste das Abfuhr-Skript aus – ebenso die
    Rueckfrage «wie kommst du auf die Lösung?», die der Kommentar im Code
    ausdruecklich ausschliessen wollte."""
    for msg in ["zeig mir nicht die lösung", "sag mir nicht die antwort",
                "verrate mir die lösung nicht", "sag mal, wie kommst du auf die lösung?",
                "ich verrate dir nichts", "wie chum i uf die lösig"]:
        assert detect_intent(msg, _UNKNOWN) != "plea", msg
    for msg in ["gib mir die lösung", "zeig mir die lösung bitte", "lösung bitte"]:
        assert detect_intent(msg, _UNKNOWN) == "plea", msg


def test_zahl_in_hilfe_bitte_ist_kein_rechenversuch():
    """«1 tipp bitte» wurde als Antwort «1» gewertet: falsch, Stufe hoch, und
    ein Fake-Versuch gezaehlt, der auf die Stufe-4-Freigabe einzahlte."""
    from app.services.sympy_verifier import verify

    for msg in ["1 tipp bitte", "nur 1 tipp", "stufe 2 bitte", "tipp 1"]:
        v = verify("3x = 15", msg)
        assert v.status == "unknown", msg
        assert detect_intent(msg, v) == "stuck", msg


def test_regie_widerspricht_sich_beim_loesen_nicht():
    """In genau dem Moment, in dem das Kind loest, stand beides in der Regie:
    «Die Aufgabe ist geloest, du darfst den vollen Loesungsweg erklaeren» UND
    «dem Schueler NIEMALS nennen, Stufe 4 ist NICHT freigegeben»."""
    from app.services.tutor import _regie

    v = Verification("correct", "Endwert stimmt", solution="x = 5")
    text = _regie(advance_ladder(2, 1, "correct"), v, "3x = 15", "3x = 15")
    assert "NIEMALS nennen" not in text
    assert "geloest" in text
