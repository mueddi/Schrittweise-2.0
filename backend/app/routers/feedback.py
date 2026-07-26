"""Nutzer-Feedback: jede:r Eingeloggte kann senden, nur der Betreiber liest."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import Feedback, User
from ..schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.add(Feedback(user_id=user.id, text=payload.text.strip(), page=payload.page))
    db.commit()
    return {"ok": True}


# Browser-Meldungen, die KEINE Stoerung sind. Bisher ging jede Meldung als
# Alarm durch: 3 von 5 Alarmen der letzten 14 Tage waren die harmlose
# «ResizeObserver loop»-Warnung, die jeder Browser beim Groesse-Aendern wirft.
# Verrauschte Fehlerseiten schaut irgendwann niemand mehr an.
_HARMLOS = (
    "resizeobserver loop",
    "script error",            # Fremd-Skript ohne CORS: keine Information drin
    "non-error promise rejection captured",
)


def _harmlos(message: str) -> bool:
    low = message.lower()
    return any(m in low for m in _HARMLOS)


@router.post("/app-fehler", status_code=201)
def report_client_error(
    payload: dict,
    user: User = Depends(get_current_user),
):
    """Browser-Fehler (JS-Crash) als Stoerung im Admin sichtbar machen.

    Bewusst schlank: nur Meldung + Seite, hart gekappt; die Drosselung in
    alert.notify (pro Meldungs-Schluessel) verhindert Fluten.
    """
    from ..services import alert

    message = str((payload or {}).get("message") or "")[:300].strip()
    url = str((payload or {}).get("url") or "")[:300].strip()
    if message and not _harmlos(message):
        alert.notify("client", f"{url} – {message}", key=message[:80])
    return {"ok": True}


@router.get("", response_model=list[FeedbackOut])
def list_feedback(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Feedback, User.display_name, User.role)
        .join(User, User.id == Feedback.user_id)
        .order_by(Feedback.id.desc())
        .limit(200)
    ).all()
    out: list[FeedbackOut] = []
    for fb, name, role in rows:
        o = FeedbackOut.model_validate(fb)
        o.display_name = name
        o.role = role.value
        out.append(o)
    return out
