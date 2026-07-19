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

# check_same_thread nur fuer SQLite noetig. Bei Postgres die Session-Zeitzone
# hart auf UTC pinnen: alle Timestamp-Spalten sind naive UTC-Wandzeit – ein
# abweichendes Server-Default-TZ wuerde Link-Ablauf und Rate-Limits verschieben.
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"options": "-c timezone=utc"}

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
        ("users", "terms_accepted_at", "ALTER TABLE users ADD COLUMN terms_accepted_at TIMESTAMP"),
        ("users", "token_version", "ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL"),
        # DEFAULT TRUE: Bestandskonten (vor der Bestaetigungs-Pflicht registriert)
        # gelten als bestaetigt; NEUE Konten setzt die App explizit auf FALSE.
        ("users", "email_verified", "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT TRUE NOT NULL"),
        ("messages", "image_path", "ALTER TABLE messages ADD COLUMN image_path VARCHAR(255)"),
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

    # Daten-Migration Stufen: alte Klassen-Werte («2. Oberstufe»,
    # «Gymnasium 1./2.») auf die kanonischen Keys mittelstufe/oberstufe/
    # gymnasium abbilden. Idempotent – trifft nur Alt-Werte.
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE users SET grade_level='gymnasium' "
                "WHERE grade_level LIKE '%ymnasium%' AND grade_level != 'gymnasium'"))
            conn.execute(text(
                "UPDATE users SET grade_level='oberstufe' "
                "WHERE grade_level LIKE '%berstufe%' AND grade_level != 'oberstufe'"))
        # Bibliothek: kommagetrennte Listen zeilenweise umschreiben
        with engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT id, grade_levels FROM library_documents "
                "WHERE grade_levels LIKE '%berstufe%' OR grade_levels LIKE '%ymnasium%'"
            )).fetchall()
            for row_id, levels in rows:
                mapped = []
                for part in (levels or "").split(","):
                    p = part.strip().lower()
                    key = ("gymnasium" if "ymnasium" in p or "gym" in p
                           else "mittelstufe" if "ittelstufe" in p
                           else "oberstufe" if "berstufe" in p else part.strip())
                    if key and key not in mapped:
                        mapped.append(key)
                new_levels = ",".join(mapped)
                if new_levels != levels:
                    conn.execute(text(
                        "UPDATE library_documents SET grade_levels=:gl WHERE id=:id"),
                        {"gl": new_levels, "id": row_id})
    except Exception:
        logging.getLogger("schrittweise.db").exception("Stufen-Daten-Migration fehlgeschlagen")
