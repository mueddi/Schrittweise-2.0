"""Aggregat-Berechnung fuer die Elternansicht (on-write).

Privacy: liest NUR attempts/exercises (Zaehlwerte), nie messages. Schreibt in
die separate Tabelle progress_aggregates. Wird nach relevanten Ereignissen
(geloeste Aufgabe, Attempt-Update) aufgerufen.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attempt, Exercise, ProgressAggregate, Topic
from .timezone import LOCAL_TZ

# grobe Trend-Labels statt Noten
TREND_SITZT = "sitzt"
TREND_BESSER = "wird_besser"
TREND_UEBEN = "noch_ueben"


_TREND_LABEL = {"sitzt": "Sitzt", "wird_besser": "Wird besser", "noch_ueben": "Noch üben"}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Montag


def recompute_week(db: Session, user_id: int, ref: datetime | None = None) -> ProgressAggregate:
    ref = ref or datetime.now(timezone.utc)
    # Wochengrenzen nach lokaler Zeit (Europe/Zurich) bestimmen, fuer die DB als UTC.
    ref_local = ref.astimezone(LOCAL_TZ) if ref.tzinfo else ref.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    ws = _week_start(ref_local.date())
    week_start_dt = datetime(ws.year, ws.month, ws.day, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    week_end_dt = week_start_dt + timedelta(days=7)

    attempts = list(
        db.scalars(
            select(Attempt).where(
                Attempt.user_id == user_id,
                Attempt.created_at >= week_start_dt,
                Attempt.created_at < week_end_dt,
            )
        )
    )

    total = len(attempts)
    solved = [a for a in attempts if a.solved]
    solved_count = len(solved)
    # Selbstaendigkeit: gelöst mit niedriger Hinweis-Stufe (<=2) = selbstaendig
    autonomous = [a for a in solved if a.hint_level <= 2]
    autonomy = (len(autonomous) / solved_count) if solved_count else 0.0

    # aktive Tage (Mo..So) + Balken
    daily = [0] * 7
    active_days_set = set()
    for a in attempts:
        d = a.created_at
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        idx = (d.astimezone(LOCAL_TZ).date() - ws).days
        if 0 <= idx < 7:
            daily[idx] += 1
            active_days_set.add(idx)

    # Stolpersteine: Themen mit vielen genutzten Hinweisen / ungeloest.
    # Aufgaben ohne Themen-Zuordnung landen im Sammel-Eintrag «Ohne Thema» –
    # sonst wirkt die Karte bei Nutzern ohne Themen faelschlich immer leer.
    heavy: Counter = Counter()
    totals: Counter = Counter()
    ex_ids = {a.exercise_id for a in attempts}
    if ex_ids:
        ex_topic = dict(db.execute(select(Exercise.id, Exercise.topic_id).where(Exercise.id.in_(ex_ids))).all())
        topic_names = dict(db.execute(select(Topic.id, Topic.name).where(Topic.user_id == user_id)).all())
        for a in attempts:
            tid = ex_topic.get(a.exercise_id)
            name = topic_names.get(tid, "Thema") if tid is not None else "Ohne Thema"
            totals[name] += 1
            if not a.solved or a.hint_level >= 3:
                heavy[name] += 1
    top_struggles = [
        {"topic": name, "heavy": count, "total": totals[name], "trend": TREND_UEBEN}
        for name, count in heavy.most_common(3)
    ]

    agg = db.scalar(
        select(ProgressAggregate).where(
            ProgressAggregate.user_id == user_id, ProgressAggregate.week_start == ws
        )
    )
    if agg is None:
        agg = ProgressAggregate(user_id=user_id, week_start=ws)
        db.add(agg)
    agg.autonomy_rate = round(autonomy, 3)
    agg.solved_count = solved_count
    agg.active_days = len(active_days_set)
    agg.top_struggles = top_struggles
    agg.daily_activity = daily
    db.flush()
    return agg


def build_summary(db: Session, student, ref: datetime | None = None) -> dict:
    """Eltern-Zusammenfassung – liest NUR Aggregate, nie messages.

    Berechnet die aktuelle Woche frisch und vergleicht mit der Vorwoche
    (Dranbleiben-Trend). Respektiert die Freigabe des Schuelers.
    """
    ref = ref or datetime.now(timezone.utc)
    agg = recompute_week(db, student.id, ref)
    ref_local = ref.astimezone(LOCAL_TZ) if ref.tzinfo else ref.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    prev_ws = _week_start(ref_local.date()) - timedelta(days=7)
    prev = db.scalar(
        select(ProgressAggregate).where(
            ProgressAggregate.user_id == student.id, ProgressAggregate.week_start == prev_ws
        )
    )
    if prev and prev.solved_count:
        delta = int(round((agg.solved_count - prev.solved_count) / prev.solved_count * 100))
    else:
        # Keine (aussagekraeftige) Vorwoche -> kein irrefuehrendes «+100 % vs. Vorwoche».
        delta = 0

    # Label je Stolperstein: hat sich der Hilfe-Anteil desselben Themas
    # gegenueber der Vorwoche verbessert -> «Wird besser», sonst «Noch üben».
    prev_ratio: dict[str, float] = {}
    for s in (prev.top_struggles or []) if prev else []:
        total = s.get("total") or 0
        if total:
            prev_ratio[s.get("topic")] = (s.get("heavy") or 0) / total
    struggles = []
    for s in (agg.top_struggles or []):
        total = s.get("total") or 0
        heavy = s.get("heavy")
        ratio = (heavy / total) if (heavy is not None and total) else None
        before = prev_ratio.get(s.get("topic"))
        if ratio is not None and before is not None and ratio < before:
            label = "Wird besser"
        else:
            label = _TREND_LABEL.get(s.get("trend", ""), "Noch üben")
        struggles.append({"topic": s.get("topic", "Thema"), "label": label,
                          "heavy": heavy, "total": s.get("total")})

    # Verlauf: letzte 4 Wochen (aktuelle zuerst) fuer den Eltern-Chart
    history_rows = list(db.scalars(
        select(ProgressAggregate)
        .where(ProgressAggregate.user_id == student.id)
        .order_by(ProgressAggregate.week_start.desc())
        .limit(4)
    ))
    history = [
        {"week_start": r.week_start, "solved_count": r.solved_count,
         "autonomy_rate": int(round(r.autonomy_rate * 100)), "active_days": r.active_days}
        for r in history_rows
    ]
    return {
        "student_display_name": student.display_name,
        "grade_level": student.grade_level,
        "autonomy_rate": int(round(agg.autonomy_rate * 100)),
        "solved_count": agg.solved_count,
        "active_days": agg.active_days,
        "dranbleiben_delta": delta,
        "top_struggles": struggles,
        "daily_activity": agg.daily_activity or [0] * 7,
        "week_start": agg.week_start,
        "shared": bool(student.share_with_parents),
        "history": history,
    }
