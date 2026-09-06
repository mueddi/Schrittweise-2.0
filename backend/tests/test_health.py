"""Die Auskunft /api/health muss die Wahrheit sagen.

Vorher meldete sie "ok", solange die Konfiguration stimmte – die Datenbank
wurde nie angefasst. War Supabase weg, konnte sich kein Kind anmelden, keine
Aufgabe speichern, keinen Chat fuehren, und die Auskunft sagte trotzdem "alles
gut". Eine Ueberwachung von aussen haette den Ausfall nicht bemerkt.
"""
import pytest
from sqlalchemy.exc import OperationalError

from app import main


def test_gesunde_app_meldet_ok_und_eine_erreichbare_datenbank(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["datenbank"] is True


def test_tote_datenbank_gibt_503_und_nicht_ok(client, monkeypatch):
    """Der eigentliche Zweck: ein Monitor muss anschlagen koennen."""
    monkeypatch.setattr(main, "_datenbank_erreichbar", lambda: False)
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["datenbank"] is False
    # UptimeRobot sucht nach dem Wort "ok" – es darf jetzt NICHT dastehen.
    assert body["status"] != "ok"


def test_die_pruefung_verraet_keine_einzelheiten(client, monkeypatch):
    """Kein Fehlertext, keine Verbindungszeichenfolge nach aussen."""
    monkeypatch.setattr(main, "_datenbank_erreichbar", lambda: False)
    text = client.get("/api/health").text
    for verraeterisch in ("postgres", "psycopg", "sqlite", "password", "Traceback"):
        assert verraeterisch not in text


def test_ein_datenbankfehler_wirft_die_auskunft_nicht_um(monkeypatch):
    """Die Pruefung selbst darf nie eine Ausnahme durchlassen – sonst waere sie
    schlimmer als gar keine Pruefung (500 statt eines sauberen 503)."""
    class ToteSession:
        def __enter__(self):
            raise OperationalError("SELECT 1", {}, Exception("Verbindung weg"))

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(main, "SessionLocal", lambda: ToteSession())
    assert main._datenbank_erreichbar() is False


def test_pruefung_bleibt_billig(client, monkeypatch):
    """Die Ueberwachung ruft das alle paar Minuten auf: genau EIN Anschlag pro
    Aufruf, und nichts Teures wie Zaehlen oder Aggregate."""
    befehle = []
    echte = main._datenbank_erreichbar

    class MitschreibendeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, stmt):
            befehle.append(str(stmt))

    monkeypatch.setattr(main, "SessionLocal", lambda: MitschreibendeSession())
    assert echte() is True
    assert len(befehle) == 1
    assert befehle[0].strip().upper() == "SELECT 1"


@pytest.mark.parametrize("feld", ["status", "app", "datenbank", "mail", "zahlung"])
def test_die_bisherigen_felder_bleiben(client, feld):
    """Gegenprobe: das Frontend und der Smoke-Test lesen diese Felder."""
    assert feld in client.get("/api/health").json()
