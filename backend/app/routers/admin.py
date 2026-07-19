"""Admin-Bereich: KI-Kosten-Auswertung + Nutzer-/Guthaben-Verwaltung
(nur Betreiber-Konto).

Kosten: aggregiert die ApiUsage-Zeilen zu den Zahlen, die der Betreiber zum
Optimieren braucht: Ø/Min/Max-Kosten pro Aufgabe, Aufschluesselung nach
Aufruf-Typ und Modell, Gesamtkosten im Zeitfenster. Anthropic rechnet in
USD ab; die Anzeige rechnet mit ``usd_chf_rate`` in CHF/Rappen um.
Nutzer: Suche + manuelle Token-Gutschrift/-Korrektur (Support-Werkzeug),
jede Buchung protokolliert (TokenAdjustment).
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_admin
from ..models import ApiUsage, TokenAdjustment, User
from ..schemas import TokenAdjustRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])
log = logging.getLogger("schrittweise.admin")

KIND_LABEL = {
    "chat": "Tutor-Chat",
    "ocr": "Erkennung (Foto/Stift)",
    "suche": "KI-Suche Bibliothek",
    "variante": "Übungs-Variante",
    "generiert": "Aufgabe erstellt",
}


def _chf(usd: float) -> float:
    return round(usd * settings.usd_chf_rate, 4)


def _rappen(usd: float) -> float:
    return round(usd * settings.usd_chf_rate * 100, 2)


@router.get("/kosten")
def kosten(tage: int = Query(30, ge=1, le=365),
           user: User = Depends(require_admin), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=tage)

    # Kosten je Aufgabe: Summe aller Chat-Aufrufe derselben Exercise
    per_exercise = (
        select(ApiUsage.exercise_id, func.sum(ApiUsage.cost_usd).label("usd"))
        .where(ApiUsage.created_at >= since,
               ApiUsage.kind == "chat",
               ApiUsage.exercise_id.is_not(None))
        .group_by(ApiUsage.exercise_id)
        .subquery()
    )
    avg_usd, min_usd, max_usd, anzahl = db.execute(
        select(func.avg(per_exercise.c.usd), func.min(per_exercise.c.usd),
               func.max(per_exercise.c.usd), func.count())
    ).one()

    nach_typ = [
        {
            "typ": kind,
            "label": KIND_LABEL.get(kind, kind),
            "aufrufe": calls,
            "input_tokens": int(in_t or 0),
            "output_tokens": int(out_t or 0),
            "cache_read_tokens": int(cr or 0),
            "cache_write_tokens": int(cw or 0),
            "kosten_chf": _chf(usd or 0.0),
            "verrechnet_tokens": int(charged or 0),
        }
        for kind, calls, in_t, out_t, cr, cw, usd, charged in db.execute(
            select(ApiUsage.kind, func.count(), func.sum(ApiUsage.input_tokens),
                   func.sum(ApiUsage.output_tokens), func.sum(ApiUsage.cache_read_tokens),
                   func.sum(ApiUsage.cache_write_tokens), func.sum(ApiUsage.cost_usd),
                   func.sum(ApiUsage.charged_tokens))
            .where(ApiUsage.created_at >= since)
            .group_by(ApiUsage.kind)
            .order_by(func.sum(ApiUsage.cost_usd).desc())
        )
    ]

    nach_modell = [
        {"modell": model, "aufrufe": calls, "kosten_chf": _chf(usd or 0.0)}
        for model, calls, usd in db.execute(
            select(ApiUsage.model, func.count(), func.sum(ApiUsage.cost_usd))
            .where(ApiUsage.created_at >= since)
            .group_by(ApiUsage.model)
            .order_by(func.sum(ApiUsage.cost_usd).desc())
        )
    ]

    gesamt_usd, gesamt_aufrufe, gesamt_verrechnet = db.execute(
        select(func.sum(ApiUsage.cost_usd), func.count(), func.sum(ApiUsage.charged_tokens))
        .where(ApiUsage.created_at >= since)
    ).one()

    return {
        "zeitraum_tage": tage,
        "kurs_usd_chf": settings.usd_chf_rate,
        "pro_aufgabe": {
            "anzahl_aufgaben": int(anzahl or 0),
            "durchschnitt_rappen": _rappen(avg_usd or 0.0),
            "min_rappen": _rappen(min_usd or 0.0),
            "max_rappen": _rappen(max_usd or 0.0),
        },
        "nach_typ": nach_typ,
        "nach_modell": nach_modell,
        "gesamt": {
            "aufrufe": int(gesamt_aufrufe or 0),
            "kosten_usd": round(gesamt_usd or 0.0, 4),
            "kosten_chf": _chf(gesamt_usd or 0.0),
            # den Nutzern verrechnete Tokens (1 Token = 1 Rp.) im Zeitraum
            "verrechnet_tokens": int(gesamt_verrechnet or 0),
        },
    }


@router.get("/nutzer")
def nutzer(q: str = Query("", max_length=100),
           user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Nutzerliste mit Guthaben und Verbrauch – Support-Ansicht."""
    stmt = select(User).order_by(User.created_at.desc()).limit(200)
    if q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(needle), User.display_name.ilike(needle)))
    users = list(db.scalars(stmt))

    # Verbrauch (verrechnete Tokens) je Nutzer in einem Rutsch
    ids = [u.id for u in users]
    verbrauch = dict(db.execute(
        select(ApiUsage.user_id, func.sum(ApiUsage.charged_tokens))
        .where(ApiUsage.user_id.in_(ids))
        .group_by(ApiUsage.user_id)
    ).all()) if ids else {}

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role.value,
            "plan": u.plan.value,
            "is_admin": u.is_admin,
            "email_verified": u.email_verified,
            "token_balance": u.token_balance,
            "free_used_tokens": u.free_used_tokens or 0,
            "monthly_free_tokens": settings.free_monthly_tokens,
            "verbraucht_tokens": int(verbrauch.get(u.id) or 0),
            "erstellt": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/nutzer/{user_id}/tokens")
def tokens_anpassen(user_id: int, payload: TokenAdjustRequest,
                    admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Guthaben manuell korrigieren (Kulanz, Rueckerstattung, verpasster Webhook).

    Positive Werte schreiben gut, negative ziehen ab (Boden bei 0).
    Jede Buchung wird mit Grund + Admin protokolliert."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer nicht gefunden")

    n = payload.tokens
    db.execute(
        update(User).where(User.id == user_id).values(
            token_balance=case(
                (User.token_balance + n > 0, User.token_balance + n),
                else_=0,
            )
        )
    )
    db.add(TokenAdjustment(user_id=user_id, admin_id=admin.id,
                           tokens=n, reason=payload.grund.strip()))
    db.commit()
    db.refresh(target)
    log.info("Token-Korrektur: %+d fuer User %s durch Admin %s (%s)",
             n, user_id, admin.id, payload.grund.strip())
    return {"token_balance": target.token_balance}


@router.get("/alarme")
def alarme(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Letzte protokollierte Stoerungen (KI/OCR/Webhook) fuer den Admin-Bereich."""
    from ..models import Alert
    from ..services.alert import KIND_LABEL as ALERT_LABEL

    rows = list(db.scalars(select(Alert).order_by(Alert.id.desc()).limit(30)))
    return [
        {
            "kind": a.kind,
            "label": ALERT_LABEL.get(a.kind, a.kind),
            "detail": a.detail,
            "zeit": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
