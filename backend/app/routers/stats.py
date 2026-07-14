"""Mini-Statistik fuer die Motivation im Lern-Screen (Serie + Wochen-Erfolge)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_student
from ..models import Attempt, Message, MessageRole, User
from ..services.timezone import LOCAL_TZ

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/mini")
def mini(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """{"serie_tage": N, "geloest_woche": M} – N = zusammenhaengende Uebungstage
    bis heute (lokale Zeit), M = geloeste Aufgaben der letzten 7 Tage."""
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # Uebungstage: Tage (Europe/Zurich) mit mindestens einer Schueler-Nachricht
    stamps = db.scalars(
        select(Message.created_at)
        .join(Attempt, Message.attempt_id == Attempt.id)
        .where(Attempt.user_id == user.id,
               Message.role == MessageRole.student,
               Message.created_at >= since)
    ).all()
    days = set()
    for ts in stamps:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        days.add(ts.astimezone(LOCAL_TZ).date())

    streak = 0
    cursor = datetime.now(LOCAL_TZ).date()
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    solved_week = db.scalar(
        select(func.count(Attempt.id)).where(
            Attempt.user_id == user.id,
            Attempt.solved.is_(True),
            Attempt.created_at >= week_ago,
        )
    ) or 0

    return {"serie_tage": streak, "geloest_woche": int(solved_week)}
