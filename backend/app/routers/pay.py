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
from ..schemas import CheckoutRequest
from ..services import quota

router = APIRouter(prefix="/api/pay", tags=["pay"])
log = logging.getLogger("schrittweise.pay")

# Die Token-Pakete der Preise-Seite (Sackgeld-Modell: Einmal-Käufe, kein Abo).
# 1 Token = 1 Rappen verrechnete KI-Leistung – Paketmenge = Preis in Rappen.
PACKAGES = {
    "schnupper": {"tokens": 200, "rappen": 200, "name": "Schrittweise Schnupper-Paket – 200 Tokens"},
    "starter": {"tokens": 900, "rappen": 900, "name": "Schrittweise Starter-Paket – 900 Tokens"},
    "power": {"tokens": 1900, "rappen": 1900, "name": "Schrittweise Power-Paket – 1900 Tokens"},
}


@router.post("/checkout")
def create_checkout(payload: CheckoutRequest | None = None, user: User = Depends(require_student)):
    """Erstellt eine Stripe-Checkout-Session und gibt deren Bezahl-URL zurück."""
    if quota.blocked_unverified(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Bitte bestätige zuerst deine E-Mail-Adresse, bevor du kaufst – schau in dein Postfach.")
    if not settings.payments_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Zahlung ist noch nicht eingerichtet – bitte den Betreiber informieren.",
        )
    pkg_key = payload.package if payload else "power"
    pkg = PACKAGES.get(pkg_key)
    if pkg is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekanntes Paket.")
    base = settings.frontend_base_url.rstrip("/")
    data = {
        "mode": "payment",
        "success_url": f"{base}/app/preise?zahlung=ok",
        "cancel_url": f"{base}/app/preise?zahlung=abbruch",
        "client_reference_id": str(user.id),
        "customer_email": user.email,
        "metadata[user_id]": str(user.id),
        "metadata[package]": pkg_key,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "chf",
        "line_items[0][price_data][unit_amount]": str(pkg["rappen"]),
        "line_items[0][price_data][product_data][name]": pkg["name"],
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

    # Paket bestimmen und Betrag/Waehrung HART validieren: gutgeschrieben wird
    # nur, was exakt zum Paket passt – ein manipulierter/fremder Event kann so
    # keine Tokens erschleichen. Bei Abweichung: loggen, aber 200 zurueckgeben
    # (sonst wiederholt Stripe den Webhook endlos).
    pkg_key = (session.get("metadata") or {}).get("package") or "power"
    pkg = PACKAGES.get(pkg_key)
    amount = session.get("amount_total")
    currency = (session.get("currency") or "").lower()
    if pkg is None or amount != pkg["rappen"] or currency != "chf":
        log.error(
            "Webhook: Betrag/Waehrung passt nicht zum Paket (%s: %s %s, Session %s) – KEINE Gutschrift",
            pkg_key, amount, currency, session.get("id"),
        )
        return {"received": True}

    try:
        user_id = int(session.get("client_reference_id") or session["metadata"]["user_id"])
    except (TypeError, ValueError, KeyError):
        log.error("Webhook: Nutzer-ID fehlt oder ungueltig (Session %s)", session.get("id"))
        return {"received": True}
    user = db.get(User, user_id)
    if user is None:
        log.error("Webhook: unbekannter Nutzer %s (Session %s)", user_id, session.get("id"))
        return {"received": True}

    # Idempotenz: unique session_id – ein Stripe-Retry schreibt nicht doppelt gut.
    db.add(
        Payment(
            user_id=user.id,
            session_id=session["id"],
            amount_rappen=amount,
            tokens=pkg["tokens"],
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"received": True}  # schon verarbeitet

    db.execute(
        update(User).where(User.id == user.id).values(token_balance=User.token_balance + pkg["tokens"])
    )
    if user.plan == Plan.free:
        user.plan = Plan.token
    db.commit()
    log.info("Zahlung verbucht: Nutzer %s, +%s Tokens (%s, Session %s)", user.id, pkg["tokens"], pkg_key, session["id"])
    return {"received": True}
