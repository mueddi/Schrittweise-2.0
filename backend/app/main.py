"""Schrittweise – FastAPI-Backend (Einstiegspunkt)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import admin, auth, topics, exercises, attempts, parents, quota, library, pay, feedback


logger = logging.getLogger("schrittweise")


def _check_production_config() -> None:
    """Verhindert unsichere Konfiguration in Produktion (Vercel/Render).

    Ein Default-JWT-Secret erlaubt Token-Faelschung, ein Dev-Login-Leak den
    Account-Takeover – in Produktion beides ein harter Startfehler statt Warnung.
    """
    if not settings.is_production:
        return
    if settings.jwt_secret_is_placeholder:
        raise RuntimeError(
            "JWT_SECRET ist der Platzhalter-Wert. In Produktion einen langen "
            "Zufallswert setzen (openssl rand -hex 32), sonst sind Tokens faelschbar."
        )
    if settings.magic_link_dev_return and not settings.allow_insecure_dev_login:
        raise RuntimeError(
            "MAGIC_LINK_DEV_RETURN=true in Produktion: Login-Links wuerden im "
            "Klartext zurueckgegeben (Account-Takeover). SMTP konfigurieren und "
            "MAGIC_LINK_DEV_RETURN=false setzen – oder fuer einen bewussten "
            "Test-Deploy zusaetzlich ALLOW_INSECURE_DEV_LOGIN=true setzen."
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _check_production_config()
    init_db()
    if settings.jwt_secret_is_placeholder:
        logger.warning(
            "JWT_SECRET ist der Default-Wert – fuer den Betrieb einen langen "
            "Zufallswert setzen (openssl rand -hex 32)."
        )
    if settings.magic_link_dev_return:
        logger.warning(
            "MAGIC_LINK_DEV_RETURN=true: Login-Links werden direkt zurueckgegeben. "
            "NUR fuer Entwicklung – in Produktion ausschalten und SMTP konfigurieren!"
        )
    yield


app = FastAPI(title="Schrittweise API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload-Verzeichnis fuer Foto-Aufgaben (auf Serverless via UPLOAD_DIR=/tmp/uploads)
UPLOAD_DIR = settings.upload_path
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:  # read-only Filesystem (Serverless ohne UPLOAD_DIR-Konfiguration)
    logger.warning("Upload-Verzeichnis %s nicht beschreibbar – Foto-Upload deaktiviert.", UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "schrittweise"}


app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(exercises.router)
app.include_router(attempts.router)
app.include_router(parents.router)
app.include_router(quota.router)
app.include_router(library.router)
app.include_router(pay.router)
app.include_router(feedback.router)
app.include_router(admin.router)
