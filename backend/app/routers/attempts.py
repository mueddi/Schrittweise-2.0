"""Hinweis-Leiter-Chat: Schuelerantwort -> SymPy -> Leiter-Zustand -> Tutor (Streaming)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import require_student
from ..models import Attempt, AttemptStatus, Exercise, Message, MessageRole, User
from ..schemas import (
    AttemptOut,
    AttemptStateOut,
    ChatRequest,
    ExerciseOut,
    MessageOut,
    message_out,
)
from ..services import aggregates, tutor
from ..services.sympy_verifier import verify

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


def _load_owned(db: Session, attempt_id: int, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session nicht gefunden")
    return attempt


@router.get("/{attempt_id}", response_model=AttemptStateOut)
def get_state(attempt_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = _load_owned(db, attempt_id, user)
    ex = db.get(Exercise, attempt.exercise_id)
    msgs = list(db.scalars(select(Message).where(Message.attempt_id == attempt.id).order_by(Message.id)))
    return AttemptStateOut(
        attempt=AttemptOut.model_validate(attempt),
        messages=[message_out(m) for m in msgs],
        exercise=ExerciseOut.model_validate(ex),
    )


@router.post("/{attempt_id}/chat")
def chat(attempt_id: int, payload: ChatRequest, user: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = _load_owned(db, attempt_id, user)
    ex = db.get(Exercise, attempt.exercise_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Leere Nachricht")

    # 1) deterministische Pruefung
    verification = verify(ex.math_expression, text)

    # 2) Leiter-Zustand berechnen (Backend ist die Autoritaet).
    #    Bereits geloest -> Zustand einfrieren: keine Stufen-/Versuchs-Aenderung,
    #    der Tutor beantwortet nur noch Verstaendnisfragen / gratuliert.
    already_solved = attempt.solved
    if already_solved:
        intent = "correct" if verification.status == "correct" else "post_solved"
        # Aufgabe ist geloest -> Loesung darf der Tutor jetzt erklaeren (permit_solution=True),
        # falls der Schueler nach dem ganzen Weg fragt.
        step = tutor.LadderStep(intent, max(attempt.hint_level, 1), attempt.own_attempts, True, True)
    else:
        intent = tutor.detect_intent(text, verification)
        step = tutor.advance_ladder(attempt.hint_level, attempt.own_attempts, intent)

    # 3) Schuelernachricht speichern (mit interner Verifikation)
    student_msg = Message(
        attempt_id=attempt.id, role=MessageRole.student, text=text,
        verification=verification.to_context(),
    )
    db.add(student_msg)

    # Attempt-Zustand fortschreiben
    attempt.hint_level = step.allowed_stage
    attempt.own_attempts = step.own_attempts
    if step.solved:
        attempt.solved = True
        attempt.status = AttemptStatus.solved
    db.commit()

    # Verlauf (nur Schueler-Rolle liest hier -> require_student) fuer den LLM-Kontext
    history = [
        {"role": m.role.value, "text": m.text}
        for m in db.scalars(select(Message).where(Message.attempt_id == attempt.id).order_by(Message.id))
    ]
    ex_text, ex_expr = ex.text, ex.math_expression
    attempt_id_local = attempt.id
    user_id_local = user.id
    grade_level = user.grade_level
    # Aggregate nur beim Uebergang zu «geloest» neu rechnen, nicht bei jedem Post-Solved-Chat
    solved_now = step.solved and not already_solved

    def generate():
        parts: list[str] = []
        try:
            for chunk in tutor.stream_reply(history, step, verification, ex_text, ex_expr, grade_level):
                parts.append(chunk)
                yield chunk
        finally:
            # Auch bei Client-Abbruch (GeneratorExit) die bisherige Tutor-Antwort
            # und ggf. die Aggregate persistieren, damit kein Turn verloren geht.
            full = "".join(parts).strip() or "Erzähl mir, wie du an die Aufgabe rangehst."
            with SessionLocal() as s:
                s.add(Message(attempt_id=attempt_id_local, role=MessageRole.tutor, text=full))
                if solved_now:
                    aggregates.recompute_week(s, user_id_local)
                s.commit()

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
