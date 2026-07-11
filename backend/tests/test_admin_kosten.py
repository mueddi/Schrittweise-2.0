"""Admin-Kostenauswertung: Preisberechnung, Zugriffsschutz, Aggregate."""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import ApiUsage
from app.services.usage import cost_usd, record

from .test_library import make_admin, register_pw


# ---- Preisberechnung ----

def test_cost_usd_haiku():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd("claude-haiku-4-5", usage) == 6.00  # 1 + 5 USD


def test_cost_usd_sonnet_mit_cache():
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "cache_read_input_tokens": 1_000_000,   # 0.1x Input-Preis
        "cache_creation_input_tokens": 1_000_000,  # 1.25x Input-Preis
    }
    # 3 + 0.3 + 3.75 = 7.05 USD
    assert abs(cost_usd("claude-sonnet-4-6", usage) - 7.05) < 1e-9


def test_cost_usd_unbekanntes_modell_faellt_auf_sonnet_preis():
    usage = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert cost_usd("irgendwas-neues", usage) == 3.00


def test_record_vertraegt_kaputte_eingaben(client):
    # darf nie werfen – auch mit None-Usage oder leerem Modell
    with SessionLocal() as db:
        record(db, "chat", "", None)
        record(db, "chat", "claude-haiku-4-5", None)
        db.commit()
        assert db.query(ApiUsage).count() == 0


# ---- Endpoint ----

def _insert_usage(exercise_id, cost, kind="chat", model="claude-haiku-4-5", days_ago=0):
    with SessionLocal() as db:
        db.add(ApiUsage(
            kind=kind, model=model, exercise_id=exercise_id,
            input_tokens=100, output_tokens=50,
            cost_usd=cost,
            created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        ))
        db.commit()


def test_kosten_nur_fuer_admin(client):
    headers = register_pw(client, "mia@test.ch")
    assert client.get("/api/admin/kosten", headers=headers).status_code == 403
    assert client.get("/api/admin/kosten").status_code == 401


def test_kosten_aggregate_stimmen(client):
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")

    # Aufgabe 1: zwei Chat-Aufrufe à 0.01 USD -> 0.02 USD; Aufgabe 2: 0.06 USD
    _insert_usage(1, 0.01)
    _insert_usage(1, 0.01)
    _insert_usage(2, 0.06, model="claude-sonnet-4-6")
    # OCR ohne exercise_id zaehlt NICHT in pro_aufgabe, aber ins Gesamt
    _insert_usage(None, 0.005, kind="ocr", model="claude-sonnet-4-6")
    # Alte Zeile ausserhalb des 30-Tage-Fensters bleibt draussen
    _insert_usage(3, 9.99, days_ago=40)

    r = client.get("/api/admin/kosten?tage=30", headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()

    pa = data["pro_aufgabe"]
    assert pa["anzahl_aufgaben"] == 2
    # Kurs 0.90: 0.02 USD = 1.8 Rp., 0.06 USD = 5.4 Rp., Ø = 3.6 Rp.
    assert abs(pa["min_rappen"] - 1.8) < 0.01
    assert abs(pa["max_rappen"] - 5.4) < 0.01
    assert abs(pa["durchschnitt_rappen"] - 3.6) < 0.01

    assert data["gesamt"]["aufrufe"] == 4
    assert abs(data["gesamt"]["kosten_usd"] - 0.085) < 1e-6

    typen = {row["typ"]: row for row in data["nach_typ"]}
    assert typen["chat"]["aufrufe"] == 3
    assert typen["ocr"]["aufrufe"] == 1
    modelle = {row["modell"]: row for row in data["nach_modell"]}
    assert modelle["claude-haiku-4-5"]["aufrufe"] == 2
    assert modelle["claude-sonnet-4-6"]["aufrufe"] == 2


def test_kosten_leer_ohne_daten(client):
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")
    r = client.get("/api/admin/kosten", headers=admin)
    assert r.status_code == 200
    data = r.json()
    assert data["pro_aufgabe"]["anzahl_aufgaben"] == 0
    assert data["gesamt"]["kosten_chf"] == 0
    assert data["nach_typ"] == []


def test_admin_hat_unbegrenzte_aufgaben(client):
    """Betreiber-Konto: kein Gratis-Limit, keine Token-Abbuchung."""
    admin = register_pw(client, "chef@test.ch")
    make_admin("chef@test.ch")

    # deutlich mehr Aufgaben als das Gratis-Kontingent (5) – alle gehen durch
    for i in range(8):
        r = client.post("/api/exercises", headers=admin, json={"text": f"{i}x + 1 = {i + 2}"})
        assert r.status_code == 201, r.text

    q = client.get("/api/quota", headers=admin).json()
    assert q["unlimited"] is True
    assert q["token_balance"] == 0  # nichts abgebucht, nichts noetig
    assert q["percent_used"] == 0

    # Schueler laufen weiterhin ins Limit
    student = register_pw(client, "mia@test.ch")
    for i in range(5):
        assert client.post("/api/exercises", headers=student,
                           json={"text": f"{i}y = {i}"}).status_code == 201
    assert client.post("/api/exercises", headers=student,
                       json={"text": "z = 1"}).status_code == 402
    assert client.get("/api/quota", headers=student).json()["unlimited"] is False


def test_mock_chat_erzeugt_keine_usage_zeile(client):
    # Ohne API-Key antwortet der Mock-Tutor – es darf KEINE Kostenzeile entstehen
    headers = register_pw(client, "mia@test.ch")
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "x = 5"}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())  # Stream konsumieren, damit das finally laeuft
    with SessionLocal() as db:
        assert db.query(ApiUsage).count() == 0
