"""Pydantic-Schemas (API-Vertraege)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


# ---------- Quota ----------
class QuotaOut(BaseModel):
    plan: str
    used_this_month: int
    monthly_free_quota: int
    token_balance: int
    remaining: int  # verbleibend (free + token)
    percent_used: int


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


TokenResponse.model_rebuild()
