"""Aufgaben anlegen und Attempts (Hinweis-Leiter-Sessions) starten + Foto-OCR."""
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_student
from ..models import Attempt, Exercise, Message, MessageRole, Topic, User
from ..schemas import (
    AttemptOut,
    AttemptStateOut,
    ExerciseCreate,
    ExerciseOut,
    MessageOut,
    message_out,
    OcrResult,
)
from ..services import quota
from ..services.ocr import OcrUnavailable, get_ocr_provider
from ..services.sympy_verifier import extract_expression

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

UPLOAD_DIR = settings.upload_path
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:  # read-only Filesystem (Serverless)
    pass
ALLOWED_IMG = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/heic"}
MAX_UPLOAD = 8 * 1024 * 1024


@router.post("/ocr", response_model=OcrResult)
async def ocr_upload(request: Request, file: UploadFile = File(...), user: User = Depends(require_student)):
    """Foto hochladen -> OCR-Preview (erkannter Text + Mathe-Ausdruck)."""
    if file.content_type not in ALLOWED_IMG:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte ein Bild hochladen (PNG/JPG/WebP).")
    # Groesse VOR dem Einlesen aus dem Header pruefen (kein RAM-DoS durch Riesen-Body).
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD + 4096:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Bild zu gross (max. 8 MB).")
    # Chunk-weise lesen und bei Ueberschreitung abbrechen (falls Header fehlt/luegt).
    data = b""
    while chunk := await file.read(1024 * 256):
        data += chunk
        if len(data) > MAX_UPLOAD:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Bild zu gross (max. 8 MB).")
    # Magic-Bytes pruefen: nur echte Bilddaten akzeptieren (Content-Type ist client-gesetzt).
    try:
        from PIL import Image
        import io

        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Datei ist kein gueltiges Bild.")
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(file.content_type, ".jpg")
    # 128-Bit-Zufallsname: Bild-URL wirkt als unerratbare Capability-URL
    name = f"{secrets.token_hex(16)}{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # /tmp kann zwischen Cold-Starts leer sein
    (UPLOAD_DIR / name).write_bytes(data)
    try:
        result = get_ocr_provider().recognize(data)
    except OcrUnavailable:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Die Erkennung ist gerade nicht erreichbar – dein Geschriebenes bleibt erhalten, versuch es gleich nochmal.",
        )
    result.image_path = f"/uploads/{name}"
    return result


@router.post("", response_model=ExerciseOut, status_code=201)
def create_exercise(payload: ExerciseCreate, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if not quota.can_start_new(db, user):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "Gratis-Kontingent aufgebraucht. Lad Tokens oder warte auf den nächsten Monat.")
    if payload.topic_id is not None:
        topic = db.get(Topic, payload.topic_id)
        if topic is None or topic.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden")
    # Ohne expliziten Ausdruck versuchen, eine pruefbare Gleichung aus dem Text
    # zu ziehen («Löse 3x = 15» -> «3x = 15»); sonst waere die Aufgabe nie verifizierbar.
    math_expr = (payload.math_expression or "").strip() or None
    if math_expr is None:
        math_expr = extract_expression(payload.text)
    ex = Exercise(
        user_id=user.id,
        text=payload.text.strip(),
        math_expression=math_expr,
        topic_id=payload.topic_id,
        image_path=payload.image_path,
    )
    db.add(ex)
    db.flush()
    quota.consume(db, user)
    db.commit()
    db.refresh(ex)
    return ExerciseOut.model_validate(ex)


@router.post("/{exercise_id}/attempts", response_model=AttemptStateOut, status_code=201)
def start_attempt(exercise_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    ex = db.get(Exercise, exercise_id)
    if ex is None or ex.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aufgabe nicht gefunden")

    attempt = Attempt(exercise_id=ex.id, user_id=user.id, hint_level=0, own_attempts=0)
    db.add(attempt)
    db.flush()

    opener = Message(
        attempt_id=attempt.id,
        role=MessageRole.tutor,
        text=(f"Los geht's! Deine Aufgabe:\n\n{ex.text}\n\n"
              "Wie würdest du anfangen? Kein Stress – ich helf dir Schritt für Schritt."),
    )
    db.add(opener)
    db.commit()
    db.refresh(attempt)

    msgs = list(db.scalars(select(Message).where(Message.attempt_id == attempt.id).order_by(Message.id)))
    return AttemptStateOut(
        attempt=AttemptOut.model_validate(attempt),
        messages=[message_out(m) for m in msgs],
        exercise=ExerciseOut.model_validate(ex),
    )


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    ex = db.get(Exercise, exercise_id)
    if ex is None or ex.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aufgabe nicht gefunden")
    return ExerciseOut.model_validate(ex)
