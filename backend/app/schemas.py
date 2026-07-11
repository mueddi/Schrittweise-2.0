"""Pydantic-Schemas (API-Vertraege)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------- Auth ----------
class MagicLinkRequest(BaseModel):
    # "register" shadowt ein BaseModel-Attribut -> intern register_, im JSON weiterhin "register"
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    # True nur im «Neu hier»-Tab: erlaubt das Anlegen eines neuen Kontos.
    register_: bool = Field(default=False, alias="register")
    # Bei Erst-Registrierung optional mitgeben:
    display_name: str | None = Field(default=None, max_length=80)
    role: str = "student"  # "student" | "parent"
    grade_level: str | None = None


class MagicLinkResponse(BaseModel):
    sent: bool
    message: str
    # Nur im Dev-Modus (ohne SMTP) gefuellt, damit man sich ohne Mailserver einloggen kann:
    dev_login_url: str | None = None
    dev_token: str | None = None


class VerifyRequest(BaseModel):
    token: str


class SupabaseVerifyRequest(BaseModel):
    # Supabase-Access-Token aus dem URL-Fragment nach dem Magic-Link-Klick
    access_token: str


class PasswordRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)
    role: str = "student"  # "student" | "parent"
    grade_level: str | None = None


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordChangeRequest(BaseModel):
    # Ohne current_password nur erlaubt, wenn der Login per Mail-Link kam
    # (Passwort-vergessen-Flow) oder das Konto noch kein Passwort hat.
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    display_name: str
    role: str
    grade_level: str | None
    language: str
    plan: str
    token_balance: int
    share_with_parents: bool
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    grade_level: str | None = None
    language: str | None = None
    share_with_parents: bool | None = None


# ---------- Topics ----------
class TopicCreate(BaseModel):
    name: str = Field(max_length=120)
    category: str = "andere"
    color: str = "#6366f1"


class TopicUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    color: str | None = None


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    color: str
    created_at: datetime
    # abgeleitete Felder (grober Trend):
    exercise_count: int = 0
    solved_count: int = 0
    progress_label: str = "Neu"
    progress_pct: int = 0


# ---------- Exercises ----------
class ExerciseCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    math_expression: str | None = Field(default=None, max_length=255)
    topic_id: int | None = None
    image_path: str | None = Field(default=None, max_length=255)


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    math_expression: str | None
    topic_id: int | None
    image_path: str | None
    created_at: datetime


# ---------- Attempts / Chat ----------
class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exercise_id: int
    status: str
    hint_level: int
    own_attempts: int
    solved: bool


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    text: str
    created_at: datetime
    # Nur der grobe Pruef-Status (correct/partial/incorrect/unknown) fuer das
    # visuelle Feedback im Chat – NIE die interne Loesung.
    verification_status: str | None = None
    # Hilfe-Stufe der Tutor-Antwort (1-4) fuer das Stufen-Tag im Chat
    hint_level: int | None = None


def message_out(m) -> "MessageOut":
    """Message -> MessageOut inkl. grobem Pruef-Status (ohne Loesung)."""
    out = MessageOut.model_validate(m)
    if getattr(m, "verification", None):
        out.verification_status = m.verification.get("status")
    return out


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class AttemptStateOut(BaseModel):
    attempt: AttemptOut
    messages: list[MessageOut]
    exercise: ExerciseOut


# ---------- OCR ----------
class OcrResult(BaseModel):
    text: str
    math_expression: str | None = None
    confidence: float = 0.0
    image_path: str | None = None


# ---------- Exercise-Liste je Thema ----------
class ExerciseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    math_expression: str | None
    created_at: datetime
    latest_attempt_id: int | None = None
    solved: bool = False


# ---------- Feedback ----------
class FeedbackCreate(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    page: str | None = Field(default=None, max_length=80)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    page: str | None
    created_at: datetime
    # Absender (nur fuer die Admin-Liste angereichert)
    display_name: str = ""
    role: str = ""


# ---------- Zahlung ----------
class CheckoutRequest(BaseModel):
    # Schluessel eines Eintrags in routers.pay.PACKAGES
    package: str = Field(default="power", max_length=20)


# ---------- Quota ----------
class QuotaOut(BaseModel):
    plan: str
    used_this_month: int
    monthly_free_quota: int
    token_balance: int
    remaining: int  # verbleibend (free + token)
    percent_used: int
    # Betreiber-Konto / Schul-Plan: keine Abbuchung, unbegrenzte Aufgaben
    unlimited: bool = False


# ---------- Parent ----------
class ParentLinkCreate(BaseModel):
    pass


class ParentLinkOut(BaseModel):
    invite_code: str
    status: str


class ParentRedeem(BaseModel):
    invite_code: str


class ParentChildSummary(BaseModel):
    student_display_name: str
    grade_level: str | None
    autonomy_rate: int  # in %
    solved_count: int
    active_days: int
    dranbleiben_delta: int  # % vs. Vorwoche
    top_struggles: list[dict]
    daily_activity: list[int]
    week_start: date | None
    shared: bool  # Schueler hat Freigabe erteilt?


# ---------- Aufgaben-Bibliothek ----------
class LibraryDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    category: str
    grade_levels: list[str]
    difficulty: str
    file_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    @field_validator("grade_levels", mode="before")
    @classmethod
    def _split_grades(cls, v):
        if isinstance(v, str):
            return [g.strip() for g in v.split(",") if g.strip()]
        return v


class LibraryTopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LibraryTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    doc_count: int = 0


class LibraryDocUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    category: str | None = None
    grade_levels: list[str] | None = None
    difficulty: str | None = None


TokenResponse.model_rebuild()
