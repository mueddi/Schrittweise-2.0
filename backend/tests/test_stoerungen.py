"""Stoerungs-Seite: Einordnung «handeln / pruefen / keine» statt roher Fehlertexte."""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Alert
from app.services.stoerungen import HAEUFUNG_24H, regel_fuer, stufe_mit_haeufung

from .test_library import make_admin, register_pw


def test_programmierfehler_ist_handlungsbedarf_ueberlastung_nicht():
    """Der Fall vom 7.9.: «Modell nicht verfuegbar – ausgewichen» sah bei
    einem TypeError genauso aus wie bei Ueberlastung. Der Fehlertyp
    entscheidet jetzt."""
    code = regel_fuer("ki", "Modell claude-sonnet-5 hat nicht geantwortet – ausgewichen. "
                            "Fehler: TypeError: Messages.stream() got an unexpected keyword argument 'thinking'")
    assert code.id == "ki-code" and code.stufe == "handeln"

    last = regel_fuer("ki", "Modell claude-sonnet-5 hat nicht geantwortet – ausgewichen. "
                            "Fehler: InternalServerError: Error code: 529 - overloaded_error")
    assert last.id == "ki-ueberlastet" and last.stufe == "keine"

    # Alte Meldungen ohne Fehlertyp (vor dem 7.9.): pruefen, nicht einschlafen
    alt = regel_fuer("ki", "Modell claude-sonnet-5 war nicht verfuegbar – automatisch auf "
                           "claude-haiku-4-5 ausgewichen. Der Schueler hat eine normale Antwort bekommen")
    assert alt.id == "ki-ausweich" and alt.stufe == "pruefen"


def test_jede_art_hat_eine_einordnung():
    faelle = {
        ("ocr", "BadRequestError: Error code: 400 - `temperature` is deprecated"): ("ocr-abgelehnt", "handeln"),
        ("ocr", "APIConnectionError: Connection error"): ("ocr-ausfall", "pruefen"),
        ("webhook", "Ungueltige Stripe-Signatur"): ("webhook", "handeln"),
        ("mail", "Login-Mail nicht verschickt. Supabase HTTP 500"): ("mail", "handeln"),
        ("server", "POST /api/x – KeyError: 'y'"): ("server", "handeln"),
        ("client", "/app/lernen – ResizeObserver loop completed"): ("client-harmlos", "keine"),
        ("client", "/app/lernen – TypeError: x is undefined"): ("client", "pruefen"),
        ("ki-qualitaet", "Antwort am Token-Limit abgeschnitten"): ("qualitaet-abgeschnitten", "keine"),
        ("ki-qualitaet", "Attempt 55: (2+3)/4 = 8 -> 5/4"): ("qualitaet-rechenfehler", "keine"),
        ("kosten", "Prompt-Caching hat NICHT gegriffen"): ("kosten-cache", "pruefen"),
        ("ki", "Probepruefung fehlgeschlagen: RuntimeError: x"): ("ki-pruefung", "pruefen"),
        ("ki", "RuntimeError: api down"): ("ki-ausfall", "pruefen"),
        ("neu", "irgendwas"): ("unbekannt", "pruefen"),
    }
    for (kind, detail), (id_, stufe) in faelle.items():
        regel = regel_fuer(kind, detail)
        assert (regel.id, regel.stufe) == (id_, stufe), (kind, detail)
        assert regel.titel[0] and regel.bedeutung[0] and regel.massnahme[0]


def test_haeufung_hebt_die_stufe():
    regel = regel_fuer("ki", "Error code: 529 overloaded")
    assert stufe_mit_haeufung(regel, HAEUFUNG_24H - 1) == "keine"
    assert stufe_mit_haeufung(regel, HAEUFUNG_24H) == "pruefen"
    hoch = regel_fuer("webhook", "x")
    assert stufe_mit_haeufung(hoch, 10) == "handeln"   # hoeher als handeln gibt es nicht


def test_stoerungs_seite_buendelt_und_ordnet_ein(client):
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    jetzt = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        # Dreimal derselbe Programmierfehler heute, einmal Ueberlastung vor 5 Tagen,
        # einmal ResizeObserver, eine uralte Meldung ausserhalb des Fensters
        for h in (1, 2, 3):
            db.add(Alert(kind="ki", detail="ausgewichen. Fehler: TypeError: unexpected keyword 'thinking'",
                         created_at=jetzt - timedelta(hours=h)))
        db.add(Alert(kind="ki", detail="ausgewichen. Fehler: InternalServerError: Error code: 529",
                     created_at=jetzt - timedelta(days=5)))
        db.add(Alert(kind="client", detail="/login – ResizeObserver loop", created_at=jetzt - timedelta(days=1)))
        db.add(Alert(kind="webhook", detail="uralt", created_at=jetzt - timedelta(days=60)))
        db.commit()

    r = client.get("/api/admin/stoerungen?tage=30", headers=admin)
    assert r.status_code == 200
    data = r.json()
    assert data["meldungen_gesamt"] == 5
    assert data["stand"] == {"handeln": 1, "pruefen": 0, "keine": 2}

    erste = data["gruppen"][0]
    assert erste["id"] == "ki-code" and erste["stufe"] == "handeln"
    assert erste["anzahl"] == 3 and erste["anzahl_24h"] == 3 and erste["gehaeuft"] is True
    assert "Programmierfehler" in erste["titel"]
    assert "Vercel" in erste["massnahme"]
    assert len(erste["meldungen"]) == 3
    # Zeitstempel tragen die Zeitzone – sonst zeigt der Browser Ortszeit statt UTC
    assert erste["letzter"].endswith("+00:00")
    assert erste["meldungen"][0]["zeit"].endswith("+00:00")

    ids = [g["id"] for g in data["gruppen"]]
    assert ids == ["ki-code", "client-harmlos", "ki-ueberlastet"]

    # Kein Zugriff fuer normale Konten
    schueler = register_pw(client, "kind@test.ch")
    assert client.get("/api/admin/stoerungen", headers=schueler).status_code == 403
