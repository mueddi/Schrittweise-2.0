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

# Die Liste heisst «top_struggles» – dort steht per Definition, woran es
# hakt. Frueher standen hier zwei weitere Werte («sitzt», «wird besser»), die
# nie vergeben wurden, weil die Liste sie gar nicht enthalten kann.
TREND_UEBEN = "noch_ueben"




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

    # «Bearbeitet» ist die ehrlichere Hauptzahl als «geloest»: in der Produktion
    # sind nur 12 % aller Versuche als geloest markiert, weil der Tutor selten
    # abhakt. Eine Ansicht, die auf «geloest» aufbaut, zeigt Eltern fast immer
    # eine Null – obwohl das Kind gearbeitet hat.
    worked_count = len(attempts)
    # Eigene Rechenschritte des Kindes: der beste verfuegbare Mass fuer Aufwand,
    # und er entsteht auch dann, wenn nichts abgehakt wird.
    own_steps = sum(a.own_attempts or 0 for a in attempts)
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

    # Stolpersteine: Themen, in denen wirklich VIEL Hilfe noetig war.
    #
    # Frueher zaehlte hier «nicht geloest ODER Hilfe-Stufe >= 3». Weil nur 12 %
    # aller Versuche als geloest markiert werden, galt damit fast alles als
    # Problem (in der Produktion 40 von 44) – eine Karte, die alles rot faerbt,
    # sagt so wenig wie eine, die nichts faerbt. Jetzt zaehlt nur die tatsaechlich
    # hohe Hilfe-Stufe; «noch nicht fertig» ist kein Stolperstein, sondern normal.
    #
    # Aufgaben ohne Thema fliegen aus der Liste: «Setzen Sie bei den Aufgaben
    # ohne Thema an» war der haeufigste Tipp und half niemandem. Sie werden
    # separat gezaehlt, damit die Ansicht zur Zuordnung auffordern kann.
    heavy: Counter = Counter()
    totals: Counter = Counter()
    ohne_thema = 0
    ex_ids = {a.exercise_id for a in attempts}
    if ex_ids:
        ex_topic = dict(db.execute(select(Exercise.id, Exercise.topic_id).where(Exercise.id.in_(ex_ids))).all())
        topic_names = dict(db.execute(select(Topic.id, Topic.name).where(Topic.user_id == user_id)).all())
        for a in attempts:
            tid = ex_topic.get(a.exercise_id)
            if tid is None:
                ohne_thema += 1
                continue
            name = topic_names.get(tid, "Thema")
            totals[name] += 1
            if a.hint_level >= 3:
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
    agg.worked_count = worked_count
    agg.own_steps = own_steps
    agg.ohne_thema = ohne_thema
    agg.active_days = len(active_days_set)
    agg.top_struggles = top_struggles
    agg.daily_activity = daily
    db.flush()
    return agg


# Unter dieser Menge sagt ein Wochenvergleich nichts. Gemessen an der echten
# Datenbank: geloeste Aufgaben pro Woche waren 4, 0, 0, 3, 1 – bei solchen
# Zahlen ist jede Prozentangabe Rauschen, und war die Vorwoche 0, kam
# rechnerisch «etwa gleich» heraus, obwohl gar nicht geuebt wurde.
TREND_MINDESTMENGE = 3


def _trend(jetzt: int, vorher: int | None) -> int | None:
    """Prozent-Veraenderung – oder ``None``, wenn die Datenlage zu duenn ist.

    ``None`` heisst «wir wissen es nicht» und wird in der Ansicht auch so
    gesagt. Das ist der ganze Punkt: lieber eine ehrliche Luecke als eine
    Zahl, die Sicherheit vortaeuscht.
    """
    if vorher is None or vorher < TREND_MINDESTMENGE or jetzt < TREND_MINDESTMENGE:
        return None
    return int(round((jetzt - vorher) / vorher * 100))


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
    # Trend auf «bearbeitet», nicht auf «geloest» – und nur, wenn beide Wochen
    # genug hergeben. Sonst None: die Ansicht sagt dann «zu wenig Daten».
    delta = _trend(agg.worked_count, prev.worked_count if prev else None)

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
            label = "Noch üben"  # top_struggles enthaelt nur Themen, die noch haken
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
         "worked_count": r.worked_count,
         "autonomy_rate": int(round(r.autonomy_rate * 100)), "active_days": r.active_days}
        for r in history_rows
    ]
    return {
        "student_display_name": student.display_name,
        "grade_level": student.grade_level,
        "autonomy_rate": int(round(agg.autonomy_rate * 100)),
        "solved_count": agg.solved_count,
        "worked_count": agg.worked_count,
        "own_steps": agg.own_steps,
        "ohne_thema": agg.ohne_thema,
        "active_days": agg.active_days,
        "dranbleiben_delta": delta,
        "top_struggles": struggles,
        "worked_on": woche_aufgaben(db, student.id, ref),
        "daily_activity": agg.daily_activity or [0] * 7,
        "week_start": agg.week_start,
        "shared": bool(student.share_with_parents),
        "history": history,
    }


# Wie viel vom Aufgabentext die Eltern sehen. Genug, um die Aufgabe zu
# erkennen und danach zu fragen – nicht der ganze Wortlaut eines Fotos.
AUFGABE_MAX = 90


def woche_aufgaben(db: Session, user_id: int, ref: datetime | None = None,
                   limit: int = 12) -> list[dict]:
    """Woran das Kind diese Woche gearbeitet hat – die Antwort auf die Frage,
    die Eltern wirklich stellen.

    Bewusst konkret statt abstrakt: ein Elternteil kann mit «Bruchrechnen,
    Mittwoch, noch offen» etwas anfangen, mit «Selbstaendigkeit 67 %» nicht.

    **Privacy:** liest ausschliesslich ``attempts``/``exercises``/``topics`` –
    also den Aufgabentext, den das Kind selbst eingegeben oder fotografiert
    hat. Nie ``messages``: was im Chat steht, bleibt zwischen Kind und Tutor.
    """
    ref = ref or datetime.now(timezone.utc)
    ref_local = ref.astimezone(LOCAL_TZ) if ref.tzinfo else ref.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    ws = _week_start(ref_local.date())
    week_start_dt = datetime(ws.year, ws.month, ws.day, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    week_end_dt = week_start_dt + timedelta(days=7)

    rows = db.execute(
        select(Attempt.updated_at, Attempt.solved, Attempt.hint_level,
               Exercise.text, Topic.name)
        .join(Exercise, Exercise.id == Attempt.exercise_id)
        .outerjoin(Topic, Topic.id == Exercise.topic_id)
        .where(Attempt.user_id == user_id,
               Attempt.created_at >= week_start_dt,
               Attempt.created_at < week_end_dt)
        .order_by(Attempt.updated_at.desc())
        .limit(limit)
    ).all()

    aufgaben = []
    for updated_at, solved, hint_level, text, topic in rows:
        kurz = " ".join((text or "").split())
        if len(kurz) > AUFGABE_MAX:
            kurz = kurz[:AUFGABE_MAX].rstrip() + "…"
        aufgaben.append({
            "aufgabe": kurz or "(ohne Text)",
            "thema": topic,
            "wann": updated_at,
            "geloest": bool(solved),
            "viel_hilfe": (hint_level or 0) >= 3,
        })
    return aufgaben
