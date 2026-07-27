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
    # App-Sprache bei der Registrierung ("de"/"en") – wird im Profil gespeichert
    language: str | None = Field(default=None, max_length=8)
    # Honeypot: unsichtbares Feld im Formular – Menschen lassen es leer,
    # simple Bots fuellen es aus und fliegen auf.
    website: str = Field(default="", max_length=200)
    # Pflicht-Zustimmung zu AGB + Datenschutzerklaerung (Checkbox im Formular)
    terms_accepted: bool = False


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class AccountDeleteRequest(BaseModel):
    password: str = Field(default="", max_length=128)


class TokenAdjustRequest(BaseModel):
    """Manuelle Guthaben-Korrektur durch den Betreiber (+Gutschrift / -Abzug)."""
    tokens: int = Field(ge=-100000, le=100000)
    grund: str = Field(min_length=3, max_length=200)

    @field_validator("tokens")
    @classmethod
    def _not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("0 Tokens ergeben keine Buchung")
        return v


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
    email_verified: bool = False


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
    # Lernziele (eine pro Zeile) – Grundlage der Probepruefung.
    # ``archived_at`` steht BEWUSST nicht hier: archivieren/wiederherstellen
    # laeuft ueber die eigenen Endpunkte, nicht als Nebeneffekt eines PATCH.
    learning_goals: str | None = None


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    color: str
    learning_goals: str = ""
    archived_at: datetime | None = None
    created_at: datetime
    # abgeleitete Felder (grober Trend):
    exercise_count: int = 0
    solved_count: int = 0
    progress_label: str = "Neu"
    progress_pct: int = 0
    # Noten des Themas (nur im Detail gefuellt, in der Liste 0/None)
    grade_count: int = 0
    grade_avg: float | None = None


# ---------- Noten ----------
class GradeIn(BaseModel):
    """Note, die der Schueler selbst erfasst.

    Schweizer Skala 1.0–6.0. Die Grenzen stehen hier und nicht nur im Router,
    damit eine ungueltige Note gar nicht erst ankommt (422 statt 400).
    """
    value: float = Field(ge=1.0, le=6.0)
    taken_on: date
    topic_id: int | None = None
    label: str = Field(default="", max_length=120)


class GradeUpdate(BaseModel):
    value: float | None = Field(default=None, ge=1.0, le=6.0)
    taken_on: date | None = None
    topic_id: int | None = None
    label: str | None = Field(default=None, max_length=120)


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    value: float
    taken_on: date
    topic_id: int | None
    label: str
    source: str
    exam_id: int | None
    created_at: datetime


class GradeVerlauf(BaseModel):
    """Zeitreihe plus die zwei Zahlen, die Eltern wirklich lesen."""
    noten: list[GradeOut]
    schnitt: float | None = None
    # Schnitt der jeweils letzten/vorletzten Haelfte – gleiche Idee wie der
    # Wochen-Trend im Eltern-Dashboard (aggregates.build_summary)
    trend: str = "gleich"  # "besser" | "gleich" | "schlechter"
    bestanden_anteil: float | None = None  # Anteil Noten >= 4.0


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
    # angehaengte Zeichnung / angehaengtes Foto der Schueler-Nachricht
    image_path: str | None = None


def message_out(m) -> "MessageOut":
    """Message -> MessageOut inkl. grobem Pruef-Status (ohne Loesung)."""
    out = MessageOut.model_validate(m)
    if getattr(m, "verification", None):
        out.verification_status = m.verification.get("status")
    return out


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    # optionales Bild (Stift-Zeichnung/Foto) aus /api/exercises/ocr
    image_path: str | None = None


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
    # 1 Token = 1 Rappen verrechnete KI-Leistung
    monthly_free_tokens: int
    free_used_tokens: int
    free_left: int
    token_balance: int
    remaining: int  # verbleibend (Gratis-Rest + Guthaben)
    percent_used: int  # vom Gratis-Kontingent
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


class ParentWeek(BaseModel):
    """Eine Woche im Verlauf der Elternansicht (nur Zaehlwerte)."""
    week_start: date
    solved_count: int
    autonomy_rate: int  # in %
    active_days: int


class ParentChildSummary(BaseModel):
    student_display_name: str
    grade_level: str | None
    autonomy_rate: int  # in %
    solved_count: int
    active_days: int
    dranbleiben_delta: int  # % vs. Vorwoche
    # Eintraege: {topic, label, heavy?, total?} – heavy/total fehlen bei
    # Aggregat-Zeilen aus der Zeit vor dieser Erweiterung.
    top_struggles: list[dict]
    daily_activity: list[int]
    week_start: date | None
    shared: bool  # Schueler hat Freigabe erteilt?
    # letzte Wochen (aktuelle zuerst) fuer den Verlaufs-Chart
    history: list[ParentWeek] = []


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


# ---------- Probeprüfung ----------
class ExamVorschau(BaseModel):
    """Was eine Probeprüfung kosten würde – VOR dem Klick, ohne einen Rappen."""
    moeglich: bool
    grund: str = ""              # falls nicht möglich: warum (Klartext)
    lernziele: int = 0
    vorhandene_aufgaben: int = 0
    kosten_rappen: int = 0       # Schätzung, bewusst der obere Wert
    guthaben: int = 0            # verbleibende Tokens des Kontos


class ExamItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    question: str
    goal: str
    student_answer: str
    image_path: str | None
    verdict: str
    judged_by: str


class ExamItemAnswer(BaseModel):
    id: int
    answer: str = ""
    image_path: str | None = None


class ExamSubmit(BaseModel):
    antworten: list[ExamItemAnswer]


class ExamZiel(BaseModel):
    """Ein Lernziel mit seiner Trefferquote.

    Nur «sitzt / sitzt nicht» waere entmutigend und zu wenig: 2 von 3 richtig
    ist etwas ganz anderes als 0 von 3, und das Kind soll das sehen.
    """
    name: str
    richtig: int
    total: int


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic_id: int
    status: str
    learning_goals: str
    grade_value: float | None
    created_at: datetime
    items: list[ExamItemOut] = []
    # Auswertung (erst nach der Abgabe gefüllt)
    richtig: int = 0
    total: int = 0
    ziele: list[ExamZiel] = []

    @field_validator("status", mode="before")
    @classmethod
    def _status_wert(cls, v):
        # Enum -> String, damit die API einen schlichten Wert liefert
        return getattr(v, "value", v)
