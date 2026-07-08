"""Gemeinsame FastAPI-Dependencies: aktueller User + Rollen-Guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiges Token")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Konto nicht gefunden")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    """Nur Schueler:innen. Schuetzt Chat/Transkript-Endpoints vor der Eltern-Rolle."""
    if user.role != Role.student:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Schüler-Konten")
    return user


def require_parent(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.parent:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Eltern-Konten")
    return user
