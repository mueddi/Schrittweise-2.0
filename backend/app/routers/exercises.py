"""Aufgaben anlegen und Attempts (Hinweis-Leiter-Sessions) starten + Foto-OCR."""
import io
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_student
from ..models import Attempt, Exercise, Message, MessageRole, Topic, UploadedImage, User
from ..schemas import (
    AttemptOut,
    AttemptStateOut,
    ExerciseCreate,
    ExerciseOut,
    MessageOut,
    message_out,
    OcrResult,
)
from ..services import quota, usage
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


def _shrink_for_storage(data: bytes) -> tuple[bytes, str]:
    """Verkleinert Fotos fuer die DB-Ablage (laengste Kante 1600px, JPEG q85).

    Kleine PNGs (Stift-Eingabe) bleiben verlustfrei PNG. Haelt die Antwort des
    Bild-Endpoints sicher unter dem Vercel-Limit (~4.5 MB) und die DB schlank.
    """
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        if (img.format or "").upper() == "PNG" and len(data) <= 1024 * 1024:
            return data, "image/png"
        if max(img.size) > 1600:
            img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        # im Zweifel Original speichern – besser gross als gar kein Bild
        return data, "image/jpeg"


@router.post("/ocr", response_model=OcrResult)
async def ocr_upload(request: Request, file: UploadFile = File(...),
                     user: User = Depends(require_student), db: Session = Depends(get_db)):
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
    provider = get_ocr_provider()
    try:
        result = provider.recognize(data)
    except OcrUnavailable:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Die Erkennung ist gerade nicht erreichbar – dein Geschriebenes bleibt erhalten, versuch es gleich nochmal.",
        )
    # Bild dauerhaft in der DB ablegen – /tmp verliert Dateien bei jedem Kaltstart.
    stored, mime = _shrink_for_storage(data)
    token = secrets.token_hex(16)
    db.add(UploadedImage(user_id=user.id, token=token, mime_type=mime,
                         size_bytes=len(stored), content=stored))
    last = getattr(provider, "last_usage", None)
    if last:
        usage.record(db, "ocr", last["model"], last["usage"], user_id=user.id)
    db.commit()
    result.image_path = f"/api/exercises/images/{token}"
    return result


@router.get("/images/{token}")
def get_image(token: str, db: Session = Depends(get_db)):
    """Liefert ein gespeichertes Aufgaben-Bild. Bewusst ohne Auth: <img src>
    schickt keinen Bearer-Header; der 128-Bit-Token macht die URL unerratbar."""
    img = db.scalar(select(UploadedImage).where(UploadedImage.token == token))
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bild nicht gefunden")
    return Response(content=img.content, media_type=img.mime_type,
                    headers={"Cache-Control": "private, max-age=86400"})


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
