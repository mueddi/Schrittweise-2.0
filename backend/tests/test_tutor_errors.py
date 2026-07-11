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
