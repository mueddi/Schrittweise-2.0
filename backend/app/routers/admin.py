"""Admin-Auswertung: KI-Kosten im Ueberblick (nur Betreiber-Konto).

Aggregiert die ApiUsage-Zeilen zu den Zahlen, die der Betreiber zum
Optimieren braucht: Ø/Min/Max-Kosten pro Aufgabe, Aufschluesselung nach
Aufruf-Typ und Modell, Gesamtkosten im Zeitfenster. Anthropic rechnet in
USD ab; die Anzeige rechnet mit ``usd_chf_rate`` in CHF/Rappen um.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_admin
from ..models import ApiUsage, User

router = APIRouter(prefix="/api/admin", tags=["admin"])

KIND_LABEL = {
    "chat": "Tutor-Chat",
    "ocr": "Erkennung (Foto/Stift)",
    "suche": "KI-Suche Bibliothek",
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
