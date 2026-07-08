"""JWT-Erzeugung/-Pruefung und Token-Helfer fuer den Magic-Link."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from .config import settings


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def new_magic_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Magic-Link-Tokens werden nur gehasht gespeichert (DB-Leak != Login)."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_invite_code() -> str:
    # gut lesbarer 8-stelliger Code (keine 0/O/1/I Verwechslungen)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))
