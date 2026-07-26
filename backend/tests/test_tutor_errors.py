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


class _OkStream:
    """Stream, der sauber antwortet."""

    def __init__(self, text="Alles gut, hier dein Tipp."):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        return iter([self._text])

    @property
    def current_message_snapshot(self):
        return types.SimpleNamespace(usage=None)

    def get_final_message(self):
        return types.SimpleNamespace(usage=None, stop_reason="end_turn")


def _fake_anthropic(ctx, versuche=None):
    """``ctx``: fester Context-Manager ODER eine Funktion model -> Context-Manager.

    ``versuche``: optionale Liste, in der die angefragten Modelle landen –
    damit ein Test belegen kann, dass wirklich gewechselt wurde.
    """
    class _Messages:
        def stream(self, **kwargs):
            if versuche is not None:
                versuche.append(kwargs.get("model"))
            return ctx(kwargs.get("model")) if callable(ctx) else ctx

    class _Client:
        # timeout/max_retries kommen jetzt mit – die Attrappe muss sie schlucken
        def __init__(self, api_key, **kwargs):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Client)


def _run(monkeypatch, ctx, versuche=None, usage_out=None):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(tutor, "anthropic", _fake_anthropic(ctx, versuche))
    return "".join(tutor.stream_reply([], _STEP, _VER, "3x = 9", "3*x = 9",
                                      usage_out=usage_out))


def test_api_error_yields_honest_message(monkeypatch, caplog):
    with caplog.at_level(logging.ERROR, logger="schrittweise.tutor"):
        out = _run(monkeypatch, _FailingCtx())
    assert "technische Probleme" in out
    # Betreiber sieht es im Log – inkl. Modell, damit «nur Sonnet ueberlastet»
    # von «alles down» unterscheidbar ist
    assert "Anthropic-Stream mit" in caplog.text and "fehlgeschlagen" in caplog.text


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


def test_vordenken_wird_beim_starken_modell_abgeschaltet():
    """Sonnet 5 denkt sonst vor – und diese Tokens zaehlen gegen max_tokens.

    Real gemessen: 700 Output-Tokens verbraucht, null Zeichen Text beim
    Schueler (Nachricht 344), davor 323 Zeichen mitten in der Formel
    abgeschnitten (Nachricht 342). Haiku kennt den Schalter nicht.
    """
    from app.config import settings
    from app.services.tutor import _thinking_param

    assert _thinking_param(settings.anthropic_model_smart) == {"type": "disabled"}
    assert _thinking_param(settings.anthropic_model_default) is None


# ---- Ausfall-Schutz: Ausweich-Modell, Zeitlimit, Hilfe-Stufe ----

def test_ueberlastetes_modell_weicht_auf_das_andere_aus(monkeypatch):
    """Der haeufigste echte Fehler ist kein Totalausfall, sondern «Modell
    ueberlastet» – und der trifft immer nur EIN Modell. Dann muss das Kind
    trotzdem eine normale Antwort bekommen, nicht eine Fehlermeldung."""
    versuche = []

    def ctx_fuer(model):
        return _FailingCtx() if model == settings.anthropic_model_default else _OkStream()

    out = _run(monkeypatch, ctx_fuer, versuche)
    assert "Alles gut" in out                    # Kind bekommt eine echte Antwort
    assert "technische Probleme" not in out
    assert versuche == [settings.anthropic_model_default, settings.anthropic_model_smart]


def test_kein_wechsel_wenn_schon_text_beim_kind_ist(monkeypatch):
    """Sonst bekaeme das Kind zwei verschiedene Antworten durcheinander."""
    versuche = []
    out = _run(monkeypatch, lambda _m: _MidStream(), versuche)
    assert out.startswith("Hallo, schau mal: ")
    assert "Verbindung ist mittendrin abgebrochen" in out
    assert len(versuche) == 1, "nach begonnenem Text darf nicht gewechselt werden"


def test_kompletter_ausfall_meldet_fehler_zurueck(monkeypatch):
    """Signal an den Aufrufer: dieser Turn hat KEINE Hilfe geliefert."""
    usage_out = {}
    versuche = []
    out = _run(monkeypatch, lambda _m: _FailingCtx(), versuche, usage_out)
    assert "technische Probleme" in out
    assert usage_out.get("fehler") is True
    assert len(versuche) == 2, "beide Modelle muessen probiert worden sein"
    assert "usage" not in usage_out, "ohne Antwort darf nichts verrechnet werden"


def test_zeitlimit_liegt_unter_dem_deckel_der_plattform():
    """Vercel bricht nach 60 s ab. Wartet der Client laenger, wird die Funktion
    von aussen abgeschossen, bevor die freundliche Meldung ueberhaupt
    ausgegeben werden kann."""
    assert tutor.CLIENT_TIMEOUT < 60
    assert tutor.AUSWEICH_DEADLINE + tutor.CLIENT_TIMEOUT < 60


def test_hilfe_stufe_klettert_nicht_ohne_gelieferten_hinweis(client, monkeypatch):
    """Fall 17: die Stufe wurde VOR dem KI-Aufruf festgeschrieben. Vier
    misslungene Nachrichten schoben ein Kind so von Stufe 1 auf 4, ohne dass je
    ein Hinweis kam – und verfaelschten die Selbstaendigkeit im Eltern-Board."""
    from app.database import SessionLocal
    from app.models import Attempt, Message, MessageRole
    from app.services import alert as alert_service
    from .test_library import register_pw

    alert_service._last_sent.clear()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(tutor, "anthropic", _fake_anthropic(lambda _m: _FailingCtx()))

    headers = register_pw(client, "ausfall@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x = 15"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]

    with SessionLocal() as db:
        vorher = db.get(Attempt, aid).hint_level

    for _ in range(4):
        with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                           json={"text": "ich brauche einen tipp"}) as r:
            antwort = "".join(r.iter_text())
        assert "technische Probleme" in antwort

    with SessionLocal() as db:
        a = db.get(Attempt, aid)
        assert a.hint_level == vorher, "Stufe darf ohne gelieferten Hinweis nicht steigen"
        # Die Fehlermeldung darf kein Stufen-Etikett tragen
        tutor_msgs = db.query(Message).filter(
            Message.attempt_id == aid, Message.role == MessageRole.tutor).all()
        assert tutor_msgs, "die Meldung wird trotzdem im Verlauf gespeichert"
        assert all(m.hint_level is None for m in tutor_msgs)


def test_stufe_steigt_bei_echter_antwort_weiterhin(client, monkeypatch):
    """Gegenprobe zum Test davor – die Leiter muss normal funktionieren."""
    from app.database import SessionLocal
    from app.models import Attempt
    from .test_library import register_pw

    def fake_stream(*args, **kwargs):
        yield "Was passiert, wenn du beide Seiten durch 3 teilst?"

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "normal@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x = 15"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]

    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "ich brauche einen tipp"}) as r:
        "".join(r.iter_text())

    with SessionLocal() as db:
        assert db.get(Attempt, aid).hint_level >= 1
