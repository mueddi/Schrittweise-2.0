"""KI-Ausfaelle: ehrliche Meldung statt stillem Mock-Fallback."""
import logging
import types

from app.config import settings
from app.services import tutor
from app.services.sympy_verifier import Verification

_STEP = tutor.LadderStep("stuck", 1, 0, False, False)
_VER = Verification("unknown", "test")


class _FailingCtx:
    """Context-Manager, der beim Betreten wirft (API nicht erreichbar)."""

    def __enter__(self):
        raise RuntimeError("api down")

    def __exit__(self, *args):
        return False


class _MidStream:
    """Stream, der nach einem Chunk abbricht."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        def gen():
            yield "Hallo, schau mal: "
            raise RuntimeError("connection reset")

        return gen()


def _fake_anthropic(ctx):
    class _Messages:
        def stream(self, **kwargs):
            return ctx

    class _Client:
        def __init__(self, api_key):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Client)


def _run(monkeypatch, ctx):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(tutor, "anthropic", _fake_anthropic(ctx))
    return "".join(tutor.stream_reply([], _STEP, _VER, "3x = 9", "3*x = 9"))


def test_api_error_yields_honest_message(monkeypatch, caplog):
    with caplog.at_level(logging.ERROR, logger="schrittweise.tutor"):
        out = _run(monkeypatch, _FailingCtx())
    assert "technische Probleme" in out
    assert "Anthropic-Stream fehlgeschlagen" in caplog.text  # Betreiber sieht es im Log


def test_mid_stream_abort_gets_marker(monkeypatch):
    out = _run(monkeypatch, _MidStream())
    assert out.startswith("Hallo, schau mal: ")  # Teiltext bleibt erhalten
    assert "Verbindung ist mittendrin abgebrochen" in out  # aber klar markiert


def test_mock_only_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    out = "".join(tutor.stream_reply([], _STEP, _VER, "3x = 9", "3*x = 9"))
    assert out  # Mock antwortet weiterhin (lokale Entwicklung ohne Key)
    assert "technische Probleme" not in out


def test_ki_failure_writes_alert(client, monkeypatch):
    """KI-Ausfall landet als Stoerung im Admin-Protokoll (gedrosselt 1/h)."""
    from app.database import SessionLocal
    from app.models import Alert
    from app.services import alert as alert_svc

    alert_svc._last_sent.clear()
    _run(monkeypatch, _FailingCtx())
    with SessionLocal() as db:
        rows = db.query(Alert).all()
        assert len(rows) == 1
        assert rows[0].kind == "ki"
        assert "api down" in rows[0].detail

    # Drossel: zweiter Fehler in derselben Stunde erzeugt keine zweite Zeile
    _run(monkeypatch, _FailingCtx())
    with SessionLocal() as db:
        assert db.query(Alert).count() == 1


def test_rechenfehler_in_tutorantwort_wird_korrigiert(client, monkeypatch):
    """Falsche Zahlen-Gleichung in der Antwort -> Korrektur-Chunk im Stream,
    in der gespeicherten Message und Alarm fuer den Admin."""
    from app.database import SessionLocal
    from app.models import Alert
    from app.services import alert as alert_service, tutor
    from .test_library import register_pw

    alert_service._last_sent.clear()

    def fake_stream(*args, **kwargs):
        yield "Genau richtig! $2 \\cdot 3 = 5$"

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "korrektur@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x + 5 = 20"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]

    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "ich probiere"}) as r:
        reply = "".join(r.iter_text())
    assert "Korrektur" in reply and "6" in reply

    state = client.get(f"/api/attempts/{aid}", headers=headers).json()
    tutor_msgs = [m["text"] for m in state["messages"] if m["role"] == "tutor"]
    assert any("Korrektur" in t for t in tutor_msgs)

    with SessionLocal() as db:
        assert any(a.kind == "ki-qualitaet" for a in db.query(Alert).all())
