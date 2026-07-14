"""Chat-Lern-Erfahrung: Gymnasium-Stufen, Erklaer-anders-Intents, Variante, Serie."""
import types
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models import ApiUsage, Attempt, Message, MessageRole, User
from app.services.sympy_verifier import Verification
from app.services.tutor import detect_intent

from .test_library import make_admin, register_pw, upload

_UNKNOWN = Verification("unknown", "test")


# ---- Teil A: Gymnasium ----

def test_gymnasium_stufe_registrierbar_und_bibliothek(client):
    r = client.post("/api/auth/register",
                    json={"terms_accepted": True, "email": "gymi@test.ch",
                          "password": "drei-worte-merken", "grade_level": "Gymnasium 3./4."})
    assert r.status_code == 200
    assert r.json()["user"]["grade_level"] == "Gymnasium 3./4."

    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    assert upload(client, admin, title="Ableitungen Basics",
                  grades="Gymnasium 1./2.,Gymnasium 3./4.").status_code == 201


def test_gymnasium_regie_und_modellwahl():
    from app.services.tutor import LadderStep, _regie, pick_model

    step = LadderStep("stuck", 1, 0, False, False)
    regie = _regie(step, _UNKNOWN, "Leite f(x) ab", None, grade_level="Gymnasium 3./4.")
    assert "Matura-Niveau" in regie
    regie_sek = _regie(step, _UNKNOWN, "3x+5=20", None, grade_level="2. Oberstufe")
    assert "Sek I" in regie_sek
    # Gymi-Stoff geht ans starke Modell
    assert pick_model("Bestimme die Ableitung von f(x) = x^2", None) == settings.anthropic_model_smart


# ---- Teil B2: «Erklaer's anders» bleibt auf derselben Stufe ----

def test_erklaer_anders_ist_simpler_intent():
    for text in [
        "Kannst du es mir mit einer Skizze zeigen?",
        "Erklär es mir mit einem Beispiel aus dem Alltag.",
        "Erklär es mir mit konkreten Zahlen statt mit x.",
    ]:
        assert detect_intent(text, _UNKNOWN) == "simpler", text


# ---- Teil B3: Uebungs-Variante ----

def _fake_anthropic(monkeypatch, text="Löse 5x + 3 = 18"):
    usage = types.SimpleNamespace(input_tokens=120, output_tokens=40,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0)
    resp = types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)], usage=usage)

    class _Messages:
        def create(self, **kwargs):
            return resp

    class _Client:
        def __init__(self, api_key):
            self.messages = _Messages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")


def _solved_task(client, headers):
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers)
    return ex


def test_variante_erzeugt_neue_aufgabe_und_verrechnet(client, monkeypatch):
    _fake_anthropic(monkeypatch)
    headers = register_pw(client, "mia@test.ch")
    ex = _solved_task(client, headers)

    r = client.post(f"/api/exercises/{ex['id']}/variante", headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["exercise"]["text"] == "Löse 5x + 3 = 18"
    assert body["exercise"]["math_expression"]  # extrahiert
    assert body["attempt"]["hint_level"] == 0

    with SessionLocal() as db:
        row = db.query(ApiUsage).filter(ApiUsage.kind == "variante").one()
        assert row.charged_tokens >= 1
        u = db.query(User).filter(User.email == "mia@test.ch").one()
        assert (u.free_used_tokens or 0) >= 1  # abgebucht


def test_variante_402_bei_leerem_guthaben(client, monkeypatch):
    _fake_anthropic(monkeypatch)
    headers = register_pw(client, "mia@test.ch")
    ex = _solved_task(client, headers)
    from app.services.quota import current_month
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == "mia@test.ch").one()
        u.free_used_tokens = 50
        u.free_month = current_month()
        u.token_balance = 0
        db.commit()
    assert client.post(f"/api/exercises/{ex['id']}/variante", headers=headers).status_code == 402


def test_variante_503_ohne_api_key(client):
    headers = register_pw(client, "mia@test.ch")
    ex = _solved_task(client, headers)
    assert client.post(f"/api/exercises/{ex['id']}/variante", headers=headers).status_code == 503


# ---- Teil B4: Uebungs-Serie ----

def test_stats_mini_serie_und_wochenzaehler(client):
    headers = register_pw(client, "mia@test.ch")
    ex = _solved_task(client, headers)

    with SessionLocal() as db:
        u = db.query(User).filter(User.email == "mia@test.ch").one()
        attempt = db.query(Attempt).filter(Attempt.user_id == u.id).first()
        now = datetime.now(timezone.utc)
        # Schueler-Nachrichten heute, gestern, vorgestern -> Serie 3
        for days in (0, 1, 2):
            db.add(Message(attempt_id=attempt.id, role=MessageRole.student,
                           text=f"versuch {days}", created_at=now - timedelta(days=days)))
        attempt.solved = True
        db.commit()

    r = client.get("/api/stats/mini", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["serie_tage"] == 3
    assert data["geloest_woche"] == 1
