"""SQLAlchemy-Setup. Ueber DATABASE_URL abstrahiert – SQLite jetzt, Postgres spaeter."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from .config import settings

def _normalize_url(url: str) -> str:
    """Render/Heroku liefern postgres:// – SQLAlchemy braucht postgresql+psycopg://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_url(settings.database_url)

# check_same_thread nur fuer SQLite noetig; bei Postgres wird das Argument ignoriert.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

_engine_kwargs: dict = {"connect_args": connect_args, "pool_pre_ping": True}
if os.environ.get("VERCEL") and not DATABASE_URL.startswith("sqlite"):
    # Serverless: kein clientseitiges Connection-Pooling – sonst halten viele
    # Function-Instanzen Verbindungen offen und erschoepfen den Supabase-Pooler.
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs.pop("pool_pre_ping")

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI-Dependency: liefert eine DB-Session und schliesst sie sauber."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Erzeugt alle Tabellen (einfache Migration fuer den Start)."""
    from sqlalchemy import inspect, text

    from . import models  # noqa: F401  – Modelle registrieren

    Base.metadata.create_all(bind=engine)

    # Mini-Migrationen: create_all ergaenzt keine Spalten in bestehenden Tabellen.
    # Fehler (z.B. fehlende Owner-Rechte) duerfen den Kaltstart nicht killen –
    # dann fehlt zwar die Spalte, aber der Rest der App laeuft und das Log zeigt warum.
    import logging

    migrations = [
        ("users", "password_hash", "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"),
        ("users", "is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE NOT NULL"),
        ("messages", "hint_level", "ALTER TABLE messages ADD COLUMN hint_level INTEGER"),
        ("users", "free_used_tokens", "ALTER TABLE users ADD COLUMN free_used_tokens INTEGER DEFAULT 0 NOT NULL"),
        ("users", "free_month", "ALTER TABLE users ADD COLUMN free_month VARCHAR(7)"),
        ("api_usage", "charged_tokens", "ALTER TABLE api_usage ADD COLUMN charged_tokens INTEGER DEFAULT 0 NOT NULL"),
    ]
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, column, ddl in migrations:
        try:
            if table in tables:
                existing = {col["name"] for col in inspector.get_columns(table)}
                if column not in existing:
                    with engine.begin() as conn:
                        conn.execute(text(ddl))
        except Exception:
            logging.getLogger("schrittweise.db").exception(
                "Auto-Migration fehlgeschlagen (%s.%s)", table, column
            )
