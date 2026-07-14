"""Aufgaben-Bibliothek: Betreiber lädt Dokumente hoch, Schüler:innen suchen und öffnen sie.

Die Datei-Bytes liegen in Postgres (LargeBinary, deferred) – auf Vercel ist
/tmp flüchtig und Request/Response sind ohnehin auf ~4.5 MB begrenzt.
"""
import io
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import LibraryDocument, LibraryTopic, User
from ..schemas import LibraryDocOut, LibraryDocUpdate, LibraryTopicCreate, LibraryTopicOut
from ..services import quota, usage
from ..services.library_search import rank_documents

# Drossel fuer die KI-Suche: mehr als so viele echte KI-Aufrufe pro Nutzer
# und Stunde -> stiller ILIKE-Fallback (Suche bleibt benutzbar, kostet aber
# den Betreiber nichts mehr).
SEARCH_AI_MAX_PER_HOUR = 30

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_LIB_UPLOAD = 4 * 1024 * 1024  # Vercel-Function: ~4.5 MB Body-Limit
ALLOWED_LIB = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
DIFFICULTIES = {"leicht", "mittel", "schwer"}
GRADES = {"1. Oberstufe", "2. Oberstufe", "3. Oberstufe", "Gymnasium 1./2.", "Gymnasium 3./4."}


def _validate_meta(db: Session, title: str, description: str, category: str,
                   grade_levels: list[str], difficulty: str) -> str:
    """Validierung; gibt die normalisierte grade_levels-Zeichenkette zurück.

    Themen (``category``) sind vom Betreiber frei verwaltbar und werden gegen
    die library_topics-Tabelle geprüft.
    """
    if not title.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Titel fehlt.")
    if not description.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Beschreibung fehlt – sie ist die Basis der Suche.")
    exists = db.scalar(select(LibraryTopic.id).where(LibraryTopic.name == category))
    if exists is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unbekanntes Thema – leg es zuerst unter «Themen verwalten» an.",
        )
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Schwierigkeit.")
    grades = [g.strip() for g in grade_levels if g.strip()]
    if not grades or any(g not in GRADES for g in grades):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte gültige Klassenstufen angeben.")
    # feste Reihenfolge + Duplikate raus
    return ",".join(sorted(set(grades)))


# ---- Themen-Verwaltung (Titel frei benennbar; nur der Betreiber schreibt) ----

@router.get("/topics", response_model=list[LibraryTopicOut])
def list_topics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(LibraryDocument.category, func.count(LibraryDocument.id))
            .group_by(LibraryDocument.category)
        ).all()
    )
    topics = db.scalars(select(LibraryTopic).order_by(LibraryTopic.name)).all()
    return [
        LibraryTopicOut(id=t.id, name=t.name, doc_count=counts.get(t.name, 0)) for t in topics
    ]


@router.post("/topics", response_model=LibraryTopicOut, status_code=201)
def create_topic(payload: LibraryTopicCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    name = payload.name.strip()[:120]
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Themen-Titel fehlt.")
    dup = db.scalar(select(LibraryTopic).where(func.lower(LibraryTopic.name) == name.lower()))
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieses Thema gibt es schon.")
    topic = LibraryTopic(name=name)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return LibraryTopicOut(id=topic.id, name=topic.name, doc_count=0)


@router.patch("/topics/{topic_id}", response_model=LibraryTopicOut)
def rename_topic(topic_id: int, payload: LibraryTopicCreate,
                 user: User = Depends(require_admin), db: Session = Depends(get_db)):
    topic = db.get(LibraryTopic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    name = payload.name.strip()[:120]
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Themen-Titel fehlt.")
    dup = db.scalar(
        select(LibraryTopic).where(func.lower(LibraryTopic.name) == name.lower(), LibraryTopic.id != topic_id)
    )
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieses Thema gibt es schon.")
    old = topic.name
    topic.name = name
    # Dokumente ziehen mit um (category speichert den Themen-Namen)
    db.execute(update(LibraryDocument).where(LibraryDocument.category == old).values(category=name))
    db.commit()
    count = db.scalar(select(func.count(LibraryDocument.id)).where(LibraryDocument.category == name)) or 0
    return LibraryTopicOut(id=topic.id, name=topic.name, doc_count=count)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    topic = db.get(LibraryTopic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    in_use = db.scalar(
        select(func.count(LibraryDocument.id)).where(LibraryDocument.category == topic.name)
    ) or 0
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Das Thema hat noch {in_use} Dokument(e) – verschieb oder lösch sie zuerst.",
        )
    db.delete(topic)
    db.commit()


@router.get("", response_model=list[LibraryDocOut])
def list_documents(
    q: str = "",
    grade: str = "",
    category: str = "",
    difficulty: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(LibraryDocument)
    if category:
        stmt = stmt.where(LibraryDocument.category == category)
    if difficulty:
        stmt = stmt.where(LibraryDocument.difficulty == difficulty)
    if grade:
        stmt = stmt.where(LibraryDocument.grade_levels.like(f"%{grade}%"))
    stmt = stmt.order_by(LibraryDocument.created_at.desc()).limit(200)
    docs = list(db.scalars(stmt))

    q = q.strip()
    if not q:
        return docs

    # KI-Ranking nur fuer Konten, die auch sonst KI nutzen duerften – sonst
    # waere die Suche ein unbegrenztes Gratis-Kosten-Loch. Zusaetzlich eine
    # Stunden-Drossel pro Nutzer. Beides faellt still auf die Textsuche zurueck.
    ranked = None
    if quota.can_use_ki(user) and not quota.blocked_unverified(user):
        from datetime import datetime, timedelta, timezone

        from ..models import ApiUsage

        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_ai = db.scalar(
            select(func.count(ApiUsage.id)).where(
                ApiUsage.user_id == user.id, ApiUsage.kind == "suche",
                ApiUsage.created_at >= hour_ago,
            )
        ) or 0
        if recent_ai < SEARCH_AI_MAX_PER_HOUR:
            usage_out: dict = {}
            ranked = rank_documents(
                q,
                [
                    {
                        "id": d.id,
                        "title": d.title,
                        "description": d.description,
                        "category": d.category,
                        "grade_levels": d.grade_levels,
                        "difficulty": d.difficulty,
                    }
                    for d in docs
                ],
                usage_out,
            )
            if usage_out.get("usage") is not None:
                usage.record(db, "suche", usage_out.get("model", ""), usage_out["usage"], user_id=user.id)
                db.commit()
    if ranked is not None:
        by_id = {d.id: d for d in docs}
        return [by_id[i] for i in ranked if i in by_id]

    # Fallback ohne KI: einfache Textsuche in Titel + Beschreibung
    needle = q.lower()
    return [d for d in docs if needle in d.title.lower() or needle in d.description.lower()]


@router.get("/{doc_id}/file")
def get_document_file(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(LibraryDocument, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden.")
    # Header sind latin-1: Umlaute etc. aus dem Dateinamen entfernen
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", doc.file_name) or "dokument"
    return Response(
        content=doc.content,  # deferred: Bytes werden erst hier geladen
        media_type=doc.mime_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.post("", response_model=LibraryDocOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form("andere"),
    grade_levels: str = Form(...),  # komma-getrennt aus dem Formular
    difficulty: str = Form("mittel"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_LIB:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Erlaubt sind PDF, PNG, JPG oder WebP.")
    grades_str = _validate_meta(db, title, description, category, grade_levels.split(","), difficulty)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_LIB_UPLOAD + 8192:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Datei zu gross (max. 4 MB).")
    data = b""
    while chunk := await file.read(1024 * 256):
        data += chunk
        if len(data) > MAX_LIB_UPLOAD:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Datei zu gross (max. 4 MB).")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Datei ist leer.")

    # Magic Bytes prüfen – Content-Type ist client-gesetzt
    if file.content_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Datei ist kein gültiges PDF.")
    else:
        try:
            from PIL import Image

            Image.open(io.BytesIO(data)).verify()
        except Exception:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Datei ist kein gültiges Bild.")

    doc = LibraryDocument(
        title=title.strip()[:200],
        description=description.strip()[:4000],
        category=category,
        grade_levels=grades_str,
        difficulty=difficulty,
        file_name=(file.filename or "dokument.pdf")[:200],
        mime_type=file.content_type,
        size_bytes=len(data),
        content=data,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.patch("/{doc_id}", response_model=LibraryDocOut)
def update_document(
    doc_id: int,
    payload: LibraryDocUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    doc = db.get(LibraryDocument, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden.")
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    merged = {
        "title": data.get("title", doc.title),
        "description": data.get("description", doc.description),
        "category": data.get("category", doc.category),
        "grade_levels": data.get("grade_levels", doc.grade_levels.split(",")),
        "difficulty": data.get("difficulty", doc.difficulty),
    }
    grades_str = _validate_meta(db, **merged)
    doc.title = merged["title"].strip()[:200]
    doc.description = merged["description"].strip()[:4000]
    doc.category = merged["category"]
    doc.grade_levels = grades_str
    doc.difficulty = merged["difficulty"]
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.get(LibraryDocument, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden.")
    db.delete(doc)
    db.commit()
