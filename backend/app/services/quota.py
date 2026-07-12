"""Guthaben-Logik: 1 Token = 1 Rappen verrechnete KI-Leistung.

Jedes Konto erhaelt monatlich Gratis-Tokens (free_monthly_tokens); danach
zahlt das gekaufte Token-Guthaben. Abgebucht wird pro KI-Antwort nach den
echten Kosten mal Sicherheitsmarge (siehe services/usage.charged_tokens) –
so kann der Betreiber nie draufzahlen. Admin- und Schul-Konten sind gratis.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Plan, User
from .timezone import LOCAL_TZ


def current_month() -> str:
    """Monats-Marke nach lokaler Zeit (Europe/Zurich), z.B. "2026-07"."""
    return datetime.now(LOCAL_TZ).strftime("%Y-%m")


def is_unlimited(user: User) -> bool:
    # Betreiber-Konto (Admin) und Schul-Plan zahlen nie: unbegrenzte Aufgaben.
    return user.is_admin or user.plan == Plan.school


def _effective_free_used(user: User) -> int:
    """Verbrauchte Gratis-Tokens dieses Monats (rein lesend, ohne Rollover-Write)."""
    if user.free_month != current_month():
        return 0
    return user.free_used_tokens or 0


def quota_state(db: Session, user: User) -> dict:
    free_total = settings.free_monthly_tokens
    free_used = _effective_free_used(user)
    free_left = max(free_total - free_used, 0)
    if is_unlimited(user):
        remaining = 10**9
        percent = 0
    else:
        remaining = free_left + user.token_balance
        percent = min(int(round(free_used / free_total * 100)), 100) if free_total else 100
    return {
        "plan": user.plan.value,
        "monthly_free_tokens": free_total,
        "free_used_tokens": free_used,
        "free_left": free_left,
        "token_balance": user.token_balance,
        "remaining": remaining,
        "percent_used": percent,
        "unlimited": is_unlimited(user),
    }


def can_use_ki(user: User) -> bool:
    """Darf dieses Konto gerade eine KI-Leistung ausloesen? (rein lesend)"""
    if is_unlimited(user):
        return True
    free_total = settings.free_monthly_tokens
    if _effective_free_used(user) < free_total:
        return True
    return user.token_balance > 0


def charge(db: Session, user_id: int, tokens: int) -> None:
    """Bucht ``tokens`` ab: erst Gratis-Kontingent, Rest vom Guthaben.

    Beides in EINEM bedingten UPDATE (alle Ausdruecke lesen die alten
    Zeilenwerte) – kein Doppel-Spend-Fenster bei parallelen Requests,
    laeuft auf SQLite und Postgres. Guthaben faellt nie unter 0; wer mit
    dem letzten Token eine teure Antwort ausloest, bekommt sie noch
    (bewusst begrenzte Kulanz). Kein Commit hier – der Aufrufer committet
    zusammen mit seinen eigenen Daten (Tutor-Message + ApiUsage-Zeile).
    """
    if tokens <= 0:
        return
    cur = current_month()
    # (A) Idempotenter Monats-Rollover: der Verlierer paralleler Rollovers
    # trifft schlicht keine Zeile mehr.
    db.execute(
        update(User)
        .where(User.id == user_id)
        .where((User.free_month.is_(None)) | (User.free_month != cur))
        .values(free_used_tokens=0, free_month=cur)
    )
    # (B) Atomarer Split: Gratis-Anteil zuerst, Rest vom Guthaben (Boden 0).
    free_total = settings.free_monthly_tokens
    free_left = free_total - User.free_used_tokens
    free_part = case(
        (free_left >= tokens, tokens),
        (free_left > 0, free_left),
        else_=0,
    )
    rest = tokens - free_part
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            free_used_tokens=User.free_used_tokens + free_part,
            token_balance=case(
                (User.token_balance - rest > 0, User.token_balance - rest),
                else_=0,
            ),
        )
    )
