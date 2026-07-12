"""Nutzungsbasierte Verrechnung: 1 Token = 1 Rappen, Abbuchung pro KI-Antwort."""
from app.database import SessionLocal
from app.models import ApiUsage, User
from app.services.quota import can_use_ki, charge, current_month, quota_state
from app.services.usage import charged_tokens

from .test_library import register_pw


def _user(email: str, **fields):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        for k, v in fields.items():
            setattr(u, k, v)
        db.commit()
        db.refresh(u)
        return u


def _fresh(email: str) -> User:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one()


# ---- charged_tokens: Rappen-Mathe mit Marge ----

def test_charged_tokens_mit_marge():
    # 0.02 USD -> 0.02*0.9*100*3 = 5.4 Rp. -> aufgerundet 6 Tokens
    assert charged_tokens(0.02) == 6
    # Mini-Aufruf: mindestens 1 Token
    assert charged_tokens(0.0001) == 1
    assert charged_tokens(0.0) == 1


def test_charged_tokens_float_artefakt():
    # exakt 6.0 Rappen darf nicht durch Float-Rauschen zu 7 werden:
    # usd so gewaehlt, dass usd*0.9*100*3 == 6.0
    usd = 6.0 / (0.9 * 100 * 3)
    assert charged_tokens(usd) == 6


# ---- charge(): Gratis zuerst, dann Guthaben, Boden 0 ----

def test_charge_gratis_zuerst_dann_guthaben(client):
    register_pw(client, "mia@test.ch")
    _user("mia@test.ch", token_balance=10, free_used_tokens=48, free_month=current_month())

    with SessionLocal() as db:
        charge(db, _fresh("mia@test.ch").id, 5)  # 2 gratis uebrig -> 3 vom Guthaben
        db.commit()
    u = _fresh("mia@test.ch")
    assert u.free_used_tokens == 50
    assert u.token_balance == 7


def test_charge_boden_bei_null(client):
    register_pw(client, "mia@test.ch")
    _user("mia@test.ch", token_balance=2, free_used_tokens=50, free_month=current_month())

    with SessionLocal() as db:
        charge(db, _fresh("mia@test.ch").id, 9)  # teurer als das Guthaben
        db.commit()
    assert _fresh("mia@test.ch").token_balance == 0  # nie negativ


def test_charge_monats_rollover(client):
    register_pw(client, "mia@test.ch")
    _user("mia@test.ch", token_balance=0, free_used_tokens=50, free_month="2020-01")

    # Neuer Monat: Gratis-Kontingent wieder da, sowohl lesend ...
    assert can_use_ki(_fresh("mia@test.ch")) is True
    with SessionLocal() as db:
        state = quota_state(db, _fresh("mia@test.ch"))
    assert state["free_used_tokens"] == 0
    assert state["free_left"] == 50

    # ... als auch beim Abbuchen (Rollover schreibt die neue Monats-Marke)
    with SessionLocal() as db:
        charge(db, _fresh("mia@test.ch").id, 3)
        db.commit()
    u = _fresh("mia@test.ch")
    assert u.free_month == current_month()
    assert u.free_used_tokens == 3
    assert u.token_balance == 0


def test_charge_free_month_null_zaehlt_als_neuer_monat(client):
    register_pw(client, "mia@test.ch")
    _user("mia@test.ch", token_balance=0, free_used_tokens=50, free_month=None)
    assert can_use_ki(_fresh("mia@test.ch")) is True


# ---- HTTP-Verhalten ----

def _make_task(client, headers):
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    return client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]


def test_aufgabe_anlegen_bucht_nichts_ab(client):
    headers = register_pw(client, "mia@test.ch")
    _user("mia@test.ch", token_balance=10)
    _make_task(client, headers)
    u = _fresh("mia@test.ch")
    assert u.token_balance == 10
    assert (u.free_used_tokens or 0) == 0


def test_chat_402_bei_leerem_guthaben(client):
    headers = register_pw(client, "mia@test.ch")
    aid = _make_task(client, headers)
    _user("mia@test.ch", token_balance=0, free_used_tokens=50, free_month=current_month())

    r = client.post(f"/api/attempts/{aid}/chat", headers=headers, json={"text": "x = 5"})
    assert r.status_code == 402
    # Nichts wurde gespeichert: nur die Eroeffnungsnachricht im Verlauf
    msgs = client.get(f"/api/attempts/{aid}", headers=headers).json()["messages"]
    assert len(msgs) == 1


def test_mock_chat_bucht_nichts_ab(client):
    # Ohne API-Key (Mock-Tutor) darf kein Token abgebucht werden
    headers = register_pw(client, "mia@test.ch")
    aid = _make_task(client, headers)
    _user("mia@test.ch", token_balance=10)

    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "keine ahnung"}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    u = _fresh("mia@test.ch")
    assert u.token_balance == 10
    assert (u.free_used_tokens or 0) == 0
    with SessionLocal() as db:
        assert db.query(ApiUsage).count() == 0


def test_quota_endpoint_neue_felder(client):
    headers = register_pw(client, "mia@test.ch")
    q = client.get("/api/quota", headers=headers).json()
    assert q["monthly_free_tokens"] == 50
    assert q["free_used_tokens"] == 0
    assert q["free_left"] == 50
    assert q["remaining"] == 50
    assert q["unlimited"] is False
