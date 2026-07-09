"""Aufgaben-Bibliothek: Betreiber lädt Dokumente hoch, Schüler:innen suchen und öffnen sie.

Die Datei-Bytes liegen in Postgres (LargeBinary, deferred) – auf Vercel ist
/tmp flüchtig und Request/Response sind ohnehin auf ~4.5 MB begrenzt.
"""
import io
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import LibraryDocument, User
from ..schemas import LibraryDocOut, LibraryDocUpdate
from ..services.library_search import rank_documents

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_LIB_UPLOAD = 4 * 1024 * 1024  # Vercel-Function: ~4.5 MB Body-Limit
ALLOWED_LIB = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
CATEGORIES = {"algebra", "geometrie", "zahlen", "andere"}
DIFFICULTIES = {"leicht", "mittel", "schwer"}
GRADES = {"1. Oberstufe", "2. Oberstufe", "3. Oberstufe"}


def _validate_meta(title: str, description: str, category: str, grade_levels: list[str], difficulty: str) -> str:
    """Whitelist-Validierung; gibt die normalisierte grade_levels-Zeichenkette zurück."""
    if not title.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Titel fehlt.")
    if not description.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Beschreibung fehlt – sie ist die Basis der Suche.")
    if category not in CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Kategorie.")
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Schwierigkeit.")
    grades = [g.strip() for g in grade_levels if g.strip()]
    if not grades or any(g not in GRADES for g in grades):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte gültige Klassenstufen angeben.")
    # feste Reihenfolge + Duplikate raus
    return ",".join(sorted(set(grades)))


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
    )
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
    grades_str = _validate_meta(title, description, category, grade_levels.split(","), difficulty)

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
    grades_str = _validate_meta(**merged)
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
