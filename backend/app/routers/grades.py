"""Schulnoten des Schuelers: erfassen, ändern, Verlauf sehen.

Bewusst NUR aus der Schueler-Rolle beschreibbar (``require_student``). Das
Eltern-Dashboard liest den Verlauf über ``aggregates``/``parents`` mit, schreibt
aber nie – Noten sind die Angabe des Kindes, nicht die der Eltern.

Die Skala ist die Schweizer: 1.0 bis 6.0, 4.0 ist bestanden.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_student
from ..models import Grade, Topic, User
from ..schemas import GradeIn, GradeOut, GradeVerlauf

router = APIRouter(prefix="/api/grades", tags=["grades"])

BESTANDEN = 4.0


def _eigenes_thema(db: Session, topic_id: int | None, user: User) -> None:
    """Ein fremdes Thema darf nicht referenziert werden – sonst könnte man
    Noten in die Themenliste anderer Konten schreiben."""
    if topic_id is None:
        return
    topic = db.get(Topic, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden")


def _hole(db: Session, grade_id: int, user: User) -> Grade:
    note = db.get(Grade, grade_id)
    if note is None or note.user_id != user.id:
        # 404 statt 403: fremde IDs sollen nicht bestätigt werden
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note nicht gefunden")
    return note


def berechne_verlauf(noten: list[Grade]) -> GradeVerlauf:
    """Zeitreihe + Schnitt + Trend. Ausgelagert, damit das Eltern-Dashboard
    dieselbe Rechnung benutzen kann und nicht eine zweite Wahrheit entsteht.

    Trend = Schnitt der neueren Hälfte gegen die ältere. Erst ab 2 Noten
    sinnvoll; bei einer einzigen Note gibt es keinen Trend, nur einen Wert.
    """
    sortiert = sorted(noten, key=lambda n: (n.taken_on, n.id))
    raus = [GradeOut.model_validate(n) for n in sortiert]
    if not sortiert:
        return GradeVerlauf(noten=[], schnitt=None, trend="gleich", bestanden_anteil=None)

    werte = [n.value for n in sortiert]
    schnitt = round(sum(werte) / len(werte), 2)
    anteil = round(sum(1 for w in werte if w >= BESTANDEN) / len(werte), 2)

    trend = "gleich"
    if len(werte) >= 2:
        mitte = len(werte) // 2
        alt = werte[:mitte] or werte[:1]
        neu = werte[mitte:]
        d = (sum(neu) / len(neu)) - (sum(alt) / len(alt))
        # 0.25 Notenpunkte Schwelle: darunter ist es Rauschen und keine
        # Nachricht wert («besser» bei 4.0 -> 4.05 wäre irreführend)
        if d >= 0.25:
            trend = "besser"
        elif d <= -0.25:
            trend = "schlechter"
    return GradeVerlauf(noten=raus, schnitt=schnitt, trend=trend, bestanden_anteil=anteil)


@router.post("", response_model=GradeOut, status_code=201)
def note_anlegen(payload: GradeIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    if payload.taken_on > date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Das Datum liegt in der Zukunft.")
    _eigenes_thema(db, payload.topic_id, user)
    note = Grade(user_id=user.id, topic_id=payload.topic_id, value=payload.value,
                 taken_on=payload.taken_on, label=payload.label.strip(), source="selbst")
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/verlauf", response_model=GradeVerlauf)
def noten_verlauf(topic_id: int | None = Query(default=None),
                  user: User = Depends(require_student), db: Session = Depends(get_db)):
    q = select(Grade).where(Grade.user_id == user.id)
    if topic_id is not None:
        q = q.where(Grade.topic_id == topic_id)
    return berechne_verlauf(list(db.scalars(q)))


@router.delete("/{grade_id}", status_code=204)
def note_loeschen(grade_id: int, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    db.delete(_hole(db, grade_id, user))
    db.commit()
