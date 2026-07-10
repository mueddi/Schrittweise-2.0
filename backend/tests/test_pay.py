"""Zahlung: Checkout-Guard, Webhook-Signatur, idempotente Token-Gutschrift."""
import hashlib
import hmac
import json
import time

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.routers.pay import PACKAGE_TOKENS

from .test_library import register_pw

WEBHOOK_SECRET = "whsec_test_1234"


def signed_headers(payload: bytes, secret: str = WEBHOOK_SECRET, ts: int | None = None) -> dict:
    t = ts if ts is not None else int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return {"stripe-signature": f"t={t},v1={sig}"}


def paid_event(user_id: int, session_id: str = "cs_test_1") -> bytes:
    return json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "payment_status": "paid",
                    "client_reference_id": str(user_id),
                    "metadata": {"user_id": str(user_id)},
                    "amount_total": 1900,
                }
            },
        }
    ).encode()


def token_balance(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one().token_balance


def test_checkout_disabled_without_config(client):
    headers = register_pw(client, "mia@test.ch")
    r = client.post("/api/pay/checkout", headers=headers)
    assert r.status_code == 503


def test_webhook_credits_tokens_idempotently(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)

    headers = register_pw(client, "mia@test.ch")
    me = client.get("/api/auth/me", headers=headers).json()
    payload = paid_event(me["id"])

    # Falsche Signatur -> 400, nichts gutgeschrieben
    bad = client.post("/api/pay/webhook", content=payload,
                      headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert bad.status_code == 400
    assert token_balance("mia@test.ch") == 0

    # Abgelaufener Zeitstempel -> 400
    old = client.post("/api/pay/webhook", content=payload,
                      headers=signed_headers(payload, ts=int(time.time()) - 3600))
    assert old.status_code == 400

    # Gültig -> Tokens gutgeschrieben, Plan wechselt auf token
    ok = client.post("/api/pay/webhook", content=payload, headers=signed_headers(payload))
    assert ok.status_code == 200, ok.text
    assert token_balance("mia@test.ch") == PACKAGE_TOKENS
    assert client.get("/api/auth/me", headers=headers).json()["plan"] == "token"

    # Stripe-Retry derselben Session -> keine doppelte Gutschrift
    again = client.post("/api/pay/webhook", content=payload, headers=signed_headers(payload))
    assert again.status_code == 200
    assert token_balance("mia@test.ch") == PACKAGE_TOKENS

    # Andere Session -> weitere Gutschrift
    payload2 = paid_event(me["id"], session_id="cs_test_2")
    client.post("/api/pay/webhook", content=payload2, headers=signed_headers(payload2))
    assert token_balance("mia@test.ch") == 2 * PACKAGE_TOKENS


def test_webhook_ignores_other_events(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    register_pw(client, "mia@test.ch")

    payload = json.dumps({"type": "invoice.created", "data": {"object": {}}}).encode()
    r = client.post("/api/pay/webhook", content=payload, headers=signed_headers(payload))
    assert r.status_code == 200
    assert token_balance("mia@test.ch") == 0
