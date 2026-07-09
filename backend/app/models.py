"""Datenmodell (Kern) fuer Schrittweise.

Privacy by Design:
  * ``messages`` (Transkripte) haengen an ``attempts`` und sind ausschliesslich
    aus der Schueler-Rolle lesbar. Die Eltern-Endpoints greifen NIE auf diese
    Tabelle zu.
  * ``progress_aggregates`` ist eine SEPARATE Tabelle, die nur grobe Aggregate
    haelt. Nur sie wird der Eltern-Rolle exponiert.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    student = "student"
    parent = "parent"


class Plan(str, enum.Enum):
    free = "free"
    token = "token"
    school = "school"


class AttemptStatus(str, enum.Enum):
    active = "active"
    solved = "solved"
    abandoned = "abandoned"


class MessageRole(str, enum.Enum):
    tutor = "tutor"
    student = "student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Anzeigename statt Klarname (Privacy)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student, nullable=False)
    grade_level: Mapped[str | None] = mapped_column(String(40), nullable=True)  # z.B. "2. Oberstufe"
    language: Mapped[str] = mapped_column(String(8), default="de", nullable=False)

    # Passwort-Login (scrypt-Hash); NULL bei Alt-Konten aus der Magic-Link-Zeit
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Abo / Kontingent
    plan: Mapped[Plan] = mapped_column(Enum(Plan), default=Plan.free, nullable=False)
    token_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Privacy-Schalter: gibt der/die Schueler:in Aggregate fuer Eltern frei?
    share_with_parents: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Betreiber-Konto: darf die Aufgaben-Bibliothek verwalten
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    topics: Mapped[list[Topic]] = relationship(back_populates="user", cascade="all, delete-orphan")
    exercises: Mapped[list[Exercise]] = relationship(back_populates="user", cascade="all, delete-orphan")


class MagicLink(Base):
    """Einmal-Token fuer passwortlosen Login (Magic-Link)."""
    __tablename__ = "magic_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Topic(Base):
    """Manuell angelegter Themen-Container. Keine automatische Klassifikation."""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # grobe Kategorie fuer die Filter-Chips (vom Schueler gewaehlt)
    category: Mapped[str] = mapped_column(String(40), default="andere", nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#6366f1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="topics")
    exercises: Mapped[list[Exercise]] = relationship(back_populates="topic")


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), index=True, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # erkannter / eingegebener Mathe-Ausdruck (z.B. "3*x + 5 = 20")
    math_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="exercises")
    topic: Mapped[Topic | None] = relationship(back_populates="exercises")
    attempts: Mapped[list[Attempt]] = relationship(back_populates="exercise", cascade="all, delete-orphan")


class Attempt(Base):
    """Eine Hinweis-Leiter-Session zu einer Exercise. Backend haelt den Leiter-Zustand."""
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), default=AttemptStatus.active, nullable=False)
    # erreichte Hinweis-Stufe 0..4
    hint_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Anzahl eigener (mathe-relevanter) Antwortversuche des Schuelers
    own_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    solved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    exercise: Mapped[Exercise] = relationship(back_populates="attempts")
    messages: Mapped[list[Message]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class Message(Base):
    """Chat-Verlauf pro Attempt. NUR aus Schueler-Rolle lesbar (siehe Router-Guards)."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # feinkoerniger Score intern (0..1), nach aussen nie sichtbar
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    attempt: Mapped[Attempt] = relationship(back_populates="messages")


class ProgressAggregate(Base):
    """Separat befuellte Tabelle fuer die Elternansicht. Kein Zugriff auf Transkripte."""
    __tablename__ = "progress_aggregates"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_user_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)  # Montag der Woche

    autonomy_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0..1
    solved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Top-Stolperthemen als grobe Trends: [{"topic": "...", "trend": "noch_ueben"}]
    top_struggles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Aktivitaet pro Wochentag (Mo..So) fuer das Balkendiagramm
    daily_activity: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


class ParentLink(Base):
    """Verknuepfung Eltern-Account <-> Schueler-Account per Einladungscode."""
    __tablename__ = "parent_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    # pending = Code erstellt, noch nicht eingeloest; linked = verbunden
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    linked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LibraryDocument(Base):
    """Vom Betreiber hochgeladenes Aufgaben-Dokument (Arbeitsblatt, meist PDF).

    Die Datei-Bytes liegen direkt in Postgres (Supabase) – auf Vercel ist /tmp
    fluechtig und Uploads sind ohnehin auf ~4 MB begrenzt. ``content`` ist
    deferred, damit Listen-/Such-Queries nie die Dokumente mitladen.
    """

    __tablename__ = "library_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="andere", nullable=False)
    # komma-verbunden, z.B. "1. Oberstufe,2. Oberstufe"
    grade_levels: Mapped[str] = mapped_column(String(80), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="mittel", nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
