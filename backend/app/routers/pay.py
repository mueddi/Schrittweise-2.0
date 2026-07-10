"""Token-Paket-Kauf über Stripe Checkout.

Ablauf: Frontend ruft /checkout auf -> Stripe-Bezahlseite (Karte/TWINT) ->
Stripe meldet die Zahlung per signiertem Webhook -> Tokens werden gutgeschrieben.
Die Stripe-API wird direkt über httpx angesprochen (form-encoded REST), die
Webhook-Signatur (HMAC-SHA256) wird mit der Standardbibliothek geprüft –
keine zusätzliche SDK-Abhängigkeit.
"""
import hashlib
import hmac
import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_student
from ..models import Payment, Plan, User

router = APIRouter(prefix="/api/pay", tags=["pay"])
log = logging.getLogger("schrittweise.pay")

# Das eine Produkt der Preise-Seite: Token-Paket
PACKAGE_TOKENS = 300
PACKAGE_RAPPEN = 1900  # CHF 19.00
PACKAGE_NAME = "Schrittweise Token-Paket – 300 Aufgaben"


@router.post("/checkout")
def create_checkout(user: User = Depends(require_student)):
    """Erstellt eine Stripe-Checkout-Session und gibt deren Bezahl-URL zurück."""
    if not settings.payments_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Zahlung ist noch nicht eingerichtet – bitte den Betreiber informieren.",
        )
    base = settings.frontend_base_url.rstrip("/")
    data = {
        "mode": "payment",
        "success_url": f"{base}/app/preise?zahlung=ok",
        "cancel_url": f"{base}/app/preise?zahlung=abbruch",
        "client_reference_id": str(user.id),
        "customer_email": user.email,
        "metadata[user_id]": str(user.id),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "chf",
        "line_items[0][price_data][unit_amount]": str(PACKAGE_RAPPEN),
        "line_items[0][price_data][product_data][name]": PACKAGE_NAME,
    }
    try:
        resp = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=data,
            auth=(settings.stripe_secret_key, ""),
            timeout=20,
        )
    except httpx.HTTPError:
        log.exception("Stripe nicht erreichbar")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Zahlungsanbieter nicht erreichbar – versuch es gleich nochmal.")
    if resp.status_code != 200:
        log.error("Stripe-Checkout fehlgeschlagen: HTTP %s – %s", resp.status_code, resp.text[:400])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Zahlung konnte nicht gestartet werden – versuch es gleich nochmal.")
    return {"url": resp.json()["url"]}


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
    """Prüft die Stripe-Webhook-Signatur (t=…,v1=… / HMAC-SHA256 über 't.payload')."""
    try:
        pairs = [kv.split("=", 1) for kv in sig_header.split(",") if "=" in kv]
        timestamp = next(int(v) for k, v in pairs if k == "t")
        v1_signatures = [v for k, v in pairs if k == "v1"]
        if not v1_signatures or abs(time.time() - timestamp) > tolerance:
            return False
        expected = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
        ).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in v1_signatures)
    except Exception:
        return False


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Von Stripe aufgerufen. Schreibt Tokens gut – idempotent pro Checkout-Session."""
    if not settings.payments_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Zahlung nicht konfiguriert.")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not verify_stripe_signature(payload, sig, settings.stripe_webhook_secret):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ungültige Signatur.")

    event = json.loads(payload)
    if event.get("type") != "checkout.session.completed":
        return {"received": True}
    session = event["data"]["object"]
    if session.get("payment_status") != "paid":
        return {"received": True}

    user_id = int(session.get("client_reference_id") or session["metadata"]["user_id"])
    user = db.get(User, user_id)
    if user is None:
        log.error("Webhook: unbekannter Nutzer %s (Session %s)", user_id, session.get("id"))
        return {"received": True}

    # Idempotenz: unique session_id – ein Stripe-Retry schreibt nicht doppelt gut.
    db.add(
        Payment(
            user_id=user.id,
            session_id=session["id"],
            amount_rappen=session.get("amount_total") or PACKAGE_RAPPEN,
            tokens=PACKAGE_TOKENS,
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"received": True}  # schon verarbeitet

    db.execute(
        update(User).where(User.id == user.id).values(token_balance=User.token_balance + PACKAGE_TOKENS)
    )
    if user.plan == Plan.free:
        user.plan = Plan.token
    db.commit()
    log.info("Zahlung verbucht: Nutzer %s, +%s Tokens (Session %s)", user.id, PACKAGE_TOKENS, session["id"])
    return {"received": True}
