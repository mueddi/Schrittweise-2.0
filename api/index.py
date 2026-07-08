"""Vercel-Serverless-Einstieg: laedt das FastAPI-Backend als ASGI-App.

Vercel erkennt `app` in api/index.py und betreibt es als Python-Function.
Secrets kommen aus den Vercel-Umgebungsvariablen; fuer MCP-Deploys ohne
Dashboard-Zugriff kann zusaetzlich eine (gitignorte) api/runtime-env.json
mitgeliefert werden – echte Werte gehoeren NIE ins Repo.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# Supabase-Auth-Anbindung (Login-Mails): URL + Publishable Key sind PUBLIC
# (stehen sonst sichtbar in jedem Frontend) und gehören zu diesem Projekt.
# Vor dem Sidecar gesetzt, damit ein versehentlich beschädigter Secret-Wert
# sie nicht überschreiben kann; echte Vercel-Env-Variablen gewinnen weiterhin.
os.environ.setdefault("SUPABASE_URL", "https://bogrqbazqjvjpahuecon.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "sb_publishable_Y1lYSALGd8Wdg_HoDjf0cA_217R27Ne")

# Optionales Secrets-Sidecar (nur falls beim Deploy mitgeliefert, gitignored)
_env_file = Path(__file__).resolve().parent / "runtime-env.json"
if _env_file.exists():
    try:
        for key, value in json.loads(_env_file.read_text()).items():
            os.environ.setdefault(key, str(value))
    except (json.JSONDecodeError, OSError):
        pass

# Serverless-Defaults: nur /tmp ist beschreibbar
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")
# Sicherheits-Defaults: ohne explizite Env kein Dev-Login-Leak in Produktion.
os.environ.setdefault("MAGIC_LINK_DEV_RETURN", "false")

# Magic-Link-Mails brauchen die oeffentliche URL; von Vercel ableiten, falls nicht gesetzt.
_vercel_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
if _vercel_url and not os.environ.get("FRONTEND_BASE_URL"):
    os.environ["FRONTEND_BASE_URL"] = f"https://{_vercel_url}"


def _clean_pg_url(url: str) -> str:
    """Integrations-URL fuer psycopg saeubern: sslmode behalten, unbekannte
    Pooler-Parameter (supa=, pgbouncer=) entfernen."""
    parts = urlsplit(url)
    keep = [(k, v) for k, v in parse_qsl(parts.query) if k in {"sslmode", "connect_timeout"}]
    return urlunsplit(parts._replace(query=urlencode(keep)))


# Datenbank: DATABASE_URL > POSTGRES_URL (Vercel-Supabase-Integration) > SQLite in /tmp
if not os.environ.get("DATABASE_URL"):
    pg = os.environ.get("POSTGRES_URL", "")
    os.environ["DATABASE_URL"] = _clean_pg_url(pg) if pg else "sqlite:////tmp/schrittweise.db"

from app.config import settings  # noqa: E402  (Pfad + Env muessen vorher stehen)
from app.main import _check_production_config  # noqa: E402

# Fail-closed schon beim Kaltstart, unabhaengig davon ob die Runtime den
# ASGI-Lifespan ausfuehrt (Default-Secret / Dev-Login-Leak in Produktion).
_check_production_config()

from app.main import app  # noqa: E402

# Tabellen sofort anlegen (idempotent): nicht jede Serverless-Runtime
# fuehrt den ASGI-Lifespan aus.
from app.database import init_db  # noqa: E402

init_db()

__all__ = ["app"]
