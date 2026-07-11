"""Gratis-Kontingent-Zaehlung. Free = N Aufgaben/Monat, danach Token-Paket."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Exercise, Plan, User
from .timezone import LOCAL_TZ


def _month_start() -> datetime:
    # Monatsgrenze nach lokaler Zeit (Europe/Zurich), als UTC fuer den DB-Vergleich.
    now_local = datetime.now(LOCAL_TZ)
    local_first = datetime(now_local.year, now_local.month, 1, tzinfo=LOCAL_TZ)
    return local_first.astimezone(timezone.utc)


def used_this_month(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(Exercise.id)).where(
            Exercise.user_id == user_id, Exercise.created_at >= _month_start()
        )
    ) or 0


def _unlimited(user: User) -> bool:
    # Betreiber-Konto (Admin) und Schul-Plan zahlen nie: unbegrenzte Aufgaben.
    return user.is_admin or user.plan == Plan.school


def quota_state(db: Session, user: User) -> dict:
    used = used_this_month(db, user.id)
    free = settings.free_monthly_quota
    if _unlimited(user):
        remaining = 10**9
        percent = 0
    else:
        free_left = max(free - used, 0)
        remaining = free_left + user.token_balance
        percent = min(int(round(used / free * 100)), 100) if free else 0
    return {
        "plan": user.plan.value,
        "used_this_month": used,
        "monthly_free_quota": free,
        "token_balance": user.token_balance,
        "remaining": remaining,
        "percent_used": percent,
        "unlimited": _unlimited(user),
    }


def can_start_new(db: Session, user: User) -> bool:
    if _unlimited(user):
        return True
    if used_this_month(db, user.id) < settings.free_monthly_quota:
        return True
    return user.token_balance > 0


def consume(db: Session, user: User) -> None:
    """Bucht eine Aufgabe ab: erst Gratis-Kontingent, dann Tokens."""
    if _unlimited(user):
        return
    # Aufgabe ist bereits angelegt und mitgezaehlt; nur ueber dem Gratis-Limit Token abbuchen.
    if used_this_month(db, user.id) > settings.free_monthly_quota:
        # Atomar dekrementieren (kein Lost-Update bei parallelen Requests, nie < 0).
        db.execute(
            update(User).where(User.id == user.id, User.token_balance > 0)
            .values(token_balance=User.token_balance - 1)
        )
        db.refresh(user)
