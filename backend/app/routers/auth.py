"""Auth per Magic-Link (passwortlos) + JWT."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import bearer, get_current_user
from ..models import LoginAttempt, MagicLink, Role, User
from ..schemas import (
    MagicLinkRequest,
    MagicLinkResponse,
    PasswordChangeRequest,
    PasswordLoginRequest,
    PasswordRegisterRequest,
    SupabaseVerifyRequest,
    TokenResponse,
    UserOut,
    UserUpdate,
    VerifyRequest,
)
from ..security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_magic_token,
    verify_password,
)
from ..services.mailer import send_magic_link
from ..services.supabase_auth import (
    SupabaseRateLimited,
    get_verified_email,
    send_magic_link_via_supabase,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

LINK_TTL_MINUTES = 30
# Rate-Limit: max. Link-Anfragen pro E-Mail im Zeitfenster (Spam-/Abuse-Schutz)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_MINUTES = 15
# Brute-Force-Schutz Passwort-Login: max. Fehlversuche pro E-Mail im Zeitfenster
LOGIN_FAIL_MAX = 8
LOGIN_FAIL_WINDOW_MINUTES = 15


# Dummy-Hash für konstante Antwortzeit bei unbekannter E-Mail (kein User-Enumeration-Timing)
_DUMMY_HASH = hash_password("nur-fuer-timing-vergleich")


@router.post("/register", response_model=TokenResponse)
def register_password(payload: PasswordRegisterRequest, db: Session = Depends(get_db)):
    """Konto mit E-Mail + Passwort anlegen und direkt einloggen."""
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if user is not None and user.password_hash:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Konto existiert bereits – wechsle zu «Anmelden»."
        )

    if user is None:
        role = Role.parent if payload.role == "parent" else Role.student
        display = (payload.display_name or email.split("@")[0]).strip()[:80]
        user = User(
            email=email,
            display_name=display,
            role=role,
            grade_level=payload.grade_level,
        )
        db.add(user)

    # Passwortloses Alt-Konto (Magic-Link-Zeit, nie eingeloggt): Passwort setzen erlaubt.
    user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)

    access = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login_password(payload: PasswordLoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    # Brute-Force-Bremse: zu viele Fehlversuche fuer diese E-Mail -> 429,
    # noch BEVOR das Passwort geprueft wird (auch ein korrektes zaehlt dann nicht).
    fail_window = datetime.now(timezone.utc) - timedelta(minutes=LOGIN_FAIL_WINDOW_MINUTES)
    fails = db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.email == email, LoginAttempt.created_at >= fail_window
        )
    ) or 0
    if fails >= LOGIN_FAIL_MAX:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Zu viele fehlgeschlagene Versuche – warte 15 Minuten und versuch es dann nochmal.",
        )

    user = db.scalar(select(User).where(User.email == email))

    stored = user.password_hash if user is not None and user.password_hash else _DUMMY_HASH
    ok = verify_password(payload.password, stored)
    if user is None or not user.password_hash or not ok:
        # Fehlversuch protokollieren; alte Eintraege gleich mit aufraeumen,
        # damit die Tabelle nicht unbegrenzt waechst.
        db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < fail_window))
        db.add(LoginAttempt(email=email))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch.")

    # Erfolg: Fehlversuchs-Zaehler dieser E-Mail zuruecksetzen
    if fails:
        db.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
        db.commit()

    access = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    """Neues Passwort setzen. Ohne aktuelles Passwort nur, wenn der Login per
    Mail-Link kam (Passwort-vergessen-Flow) oder noch kein Passwort existiert."""
    token_payload = decode_access_token(creds.credentials) if creds else None
    via_email = bool(token_payload) and token_payload.get("via") == "email"

    if user.password_hash and not via_email:
        if not payload.current_password or not verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Das aktuelle Passwort stimmt nicht."
            )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    # Frisches Token ausgeben (via=password), damit die Session normal weiterlaeuft.
    access = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/request-link", response_model=MagicLinkResponse)
def request_link(payload: MagicLinkRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    window_start = datetime.now(timezone.utc) - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    recent = db.scalar(
        select(func.count(MagicLink.id)).where(
            MagicLink.email == email, MagicLink.created_at >= window_start
        )
    ) or 0
    if recent >= RATE_LIMIT_MAX:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Zu viele Anfragen – warte ein paar Minuten und versuch es nochmal.",
        )

    user = db.scalar(select(User).where(User.email == email))

    # Erst-Registrierung nur mit explizitem register-Flag («Neu hier»-Tab),
    # sonst legt ein Tippfehler im Anmelden-Tab stillschweigend ein Geisterkonto an.
    if user is None:
        if not payload.register_:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Kein Konto mit dieser E-Mail – wechsle zu «Neu hier».",
            )
        role = Role.parent if payload.role == "parent" else Role.student
        display = (payload.display_name or email.split("@")[0]).strip()[:80]
        user = User(
            email=email,
            display_name=display,
            role=role,
            grade_level=payload.grade_level,
        )
        db.add(user)
        db.flush()

    token = new_magic_token()
    # Nur der Hash landet in der DB – ein DB-Leak erlaubt keinen Login.
    db.add(
        MagicLink(
            email=email,
            token=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=LINK_TTL_MINUTES),
        )
    )
    db.commit()

    link = f"{settings.frontend_base_url}/login/verify?token={token}"

    # Bevorzugt: Login-Mail über Supabase Auth (kein eigener SMTP-Zugang nötig).
    # Der Rückweg läuft dann über /api/auth/verify-supabase statt über `token`.
    if settings.supabase_auth_enabled:
        try:
            send_magic_link_via_supabase(email, f"{settings.frontend_base_url}/login/verify")
            return MagicLinkResponse(sent=True, message="Wir haben dir einen Link geschickt.")
        except SupabaseRateLimited:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Zu viele Login-Mails in kurzer Zeit – warte ein paar Minuten und versuch es nochmal.",
            )
        except Exception:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Mailversand momentan nicht möglich – versuch es in ein paar Minuten nochmal.",
            )

    if settings.smtp_enabled:
        try:
            if send_magic_link(email, link):
                return MagicLinkResponse(sent=True, message="Wir haben dir einen Link geschickt.")
        except Exception:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Mailversand momentan nicht möglich – versuch es in ein paar Minuten nochmal.",
            )

    # Dev-Modus ohne Mailserver: Link direkt zurueckgeben, damit Login moeglich ist.
    if settings.magic_link_dev_return:
        return MagicLinkResponse(
            sent=False,
            message="Dev-Modus: Login-Link direkt zurueckgegeben (kein Mailversand konfiguriert).",
            dev_login_url=link,
            dev_token=token,
        )
    # Produktion ohne SMTP: klarer Fehler statt stiller Sackgasse
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Login momentan nicht möglich (kein Mailversand konfiguriert). Bitte den Betreiber informieren.",
    )


@router.post("/verify", response_model=TokenResponse)
def verify(payload: VerifyRequest, db: Session = Depends(get_db)):
    ml = db.scalar(select(MagicLink).where(MagicLink.token == hash_token(payload.token)))
    if ml is None or ml.used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link ungültig oder bereits benutzt.")
    expires = ml.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link abgelaufen. Fordere einen neuen an.")

    user = db.scalar(select(User).where(User.email == ml.email))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Konto nicht gefunden.")

    # Einmal-Nutzung atomar: nur der Request, der used False->True dreht, gewinnt.
    # Verhindert, dass zwei parallele Verifikationen desselben Links beide ein Token bekommen.
    marked = db.execute(
        update(MagicLink).where(MagicLink.id == ml.id, MagicLink.used.is_(False)).values(used=True)
    )
    if marked.rowcount != 1:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link ungültig oder bereits benutzt.")
    db.commit()

    access = create_access_token(user.id, user.role.value, via="email")
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/verify-supabase", response_model=TokenResponse)
def verify_supabase(payload: SupabaseVerifyRequest, db: Session = Depends(get_db)):
    """Tauscht ein Supabase-Access-Token (aus der Login-Mail) gegen das App-JWT."""
    email = get_verified_email(payload.access_token)
    if email is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Link ungültig oder abgelaufen. Fordere einen neuen an."
        )
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Kein Konto mit dieser E-Mail – registriere dich zuerst über «Neu hier».",
        )
    access = create_access_token(user.id, user.role.value, via="email")
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # exclude_none: explizites {"display_name": null} darf keine NOT-NULL-Spalte auf None setzen (500).
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
