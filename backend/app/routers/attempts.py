"""Hinweis-Leiter-Chat: Schuelerantwort -> SymPy -> Leiter-Zustand -> Tutor (Streaming)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import require_student
from ..models import Attempt, AttemptStatus, Exercise, Message, MessageRole, UploadedImage, User
from ..schemas import (
    AttemptOut,
    AttemptStateOut,
    ChatRequest,
    ExerciseOut,
    MessageOut,
    message_out,
)
from .. import i18n
from ..services import aggregates, quota, tutor, usage
from ..services.sympy_verifier import verify

router = APIRouter(prefix="/api/attempts", tags=["attempts"])

# Frequenz-Bremse: mehr Nachrichten pro Minute schafft kein Mensch beim Lernen.
# Verhindert, dass viele PARALLELE Anfragen das Guthaben-Gate ueberholen
# (Abbuchung erfolgt erst nach der Antwort, Boden bei 0).
CHAT_MAX_PER_MINUTE = 8


def _load_owned(db: Session, attempt_id: int, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            i18n.t(i18n.lang_of(user), "Session nicht gefunden", "Session not found"))
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
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            i18n.t(i18n.lang_of(user), "Leere Nachricht", "Empty message"))

    # Frequenz-Bremse (siehe CHAT_MAX_PER_MINUTE)
    minute_ago = datetime.now(timezone.utc) - timedelta(seconds=60)
    recent_msgs = db.scalar(
        select(func.count(Message.id))
        .join(Attempt, Message.attempt_id == Attempt.id)
        .where(Attempt.user_id == user.id,
               Message.role == MessageRole.student,
               Message.created_at >= minute_ago)
    ) or 0
    lang = i18n.lang_of(user)
    if recent_msgs >= CHAT_MAX_PER_MINUTE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            i18n.t(lang,
                                   "Langsam 🙂 – eine Nachricht nach der anderen. Versuch es gleich nochmal.",
                                   "Slow down 🙂 – one message at a time. Try again in a moment."))

    # Guthaben-Gate VOR jeder Zustandsaenderung: sonst staende die Nachricht
    # ohne Antwort im Verlauf und die Leiter wuerde sich gratis weiterdrehen.
    if quota.blocked_unverified(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            i18n.t(lang,
                                   "Bitte bestätige zuerst deine E-Mail-Adresse – schau in dein Postfach.",
                                   "Please confirm your email address first – check your inbox."))
    if not quota.can_use_ki(user):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            i18n.t(lang,
                                   "Dein Guthaben ist aufgebraucht. Lad Tokens oder warte auf den nächsten Monat.",
                                   "Your balance is used up. Top up tokens or wait for next month."))

    # Angehaengtes Bild (Stift-Zeichnung/Foto aus /api/exercises/ocr) pruefen:
    # nur eigene, tatsaechlich gespeicherte Bilder duerfen an Nachrichten haengen.
    msg_image_path = None
    msg_image = None  # (bytes, mime) fuer den Tutor
    if payload.image_path:
        token = payload.image_path.rsplit("/", 1)[-1]
        img = None
        if payload.image_path.startswith("/api/exercises/images/"):
            img = db.scalar(select(UploadedImage).where(UploadedImage.token == token))
        if img is None or img.user_id != user.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bild nicht gefunden")
        msg_image_path = payload.image_path
        msg_image = (img.content, img.mime_type)

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
        verification=verification.to_context(), image_path=msg_image_path,
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
    lang_local = lang

    # Aufgaben-Figur (Foto) fuer den Tutor laden – bei Geometrie steckt die
    # halbe Aufgabe im Bild. Fehlt es (alte /tmp-Pfade), laeuft der Chat ohne.
    image = None
    if ex.image_path and ex.image_path.startswith("/api/exercises/images/"):
        token = ex.image_path.rsplit("/", 1)[-1]
        img = db.scalar(select(UploadedImage).where(UploadedImage.token == token))
        if img is not None:
            image = (img.content, img.mime_type)
    # Aggregate nur beim Uebergang zu «geloest» neu rechnen, nicht bei jedem Post-Solved-Chat
    solved_now = step.solved and not already_solved

    # Stufe der Antwort fuer die Chat-Anzeige; nach der Loesung keine Stufe mehr
    reply_level = None if already_solved else step.allowed_stage

    exercise_id_local = ex.id
    unlimited_local = quota.is_unlimited(user)

    def generate():
        parts: list[str] = []
        usage_out: dict = {}
        try:
            for chunk in tutor.stream_reply(history, step, verification, ex_text, ex_expr,
                                            grade_level, image, usage_out,
                                            last_image=msg_image, language=lang_local):
                parts.append(chunk)
                yield chunk
        finally:
            # Auch bei Client-Abbruch (GeneratorExit) die bisherige Tutor-Antwort
            # und ggf. die Aggregate persistieren, damit kein Turn verloren geht.
            full = "".join(parts).strip() or i18n.t(
                lang_local,
                "Erzähl mir, wie du an die Aufgabe rangehst.",
                "Tell me how you'd approach the task.")
            with SessionLocal() as s:
                s.add(Message(attempt_id=attempt_id_local, role=MessageRole.tutor, text=full,
                              hint_level=reply_level))
                if usage_out.get("usage") is not None:
                    # Verrechnung + Erfassung im selben Commit wie die Tutor-Message,
                    # damit charged_tokens nie vom tatsaechlich Abgebuchten abweicht.
                    charged = 0
                    if not unlimited_local:
                        charged = usage.charged_tokens(
                            usage.cost_usd(usage_out.get("model", ""), usage_out["usage"]))
                        quota.charge(s, user_id_local, charged)
                    usage.record(s, "chat", usage_out.get("model", ""), usage_out["usage"],
                                 user_id=user_id_local, exercise_id=exercise_id_local,
                                 charged=charged)
                if solved_now:
                    try:
                        aggregates.recompute_week(s, user_id_local)
                    except Exception:
                        # Aggregat-Fehler darf Tutor-Message + Abbuchung nicht wegrollen
                        import logging

                        logging.getLogger("schrittweise.attempts").exception(
                            "recompute_week fehlgeschlagen (User %s)", user_id_local)
                s.commit()

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
