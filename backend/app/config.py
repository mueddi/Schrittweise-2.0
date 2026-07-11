"""Zentrale Konfiguration via pydantic-settings (liest aus .env / Umgebung)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model_default: str = "claude-haiku-4-5"
    anthropic_model_smart: str = "claude-sonnet-4-6"

    # Auth / JWT
    jwt_secret: str = "dev-secret-nur-fuer-lokal-nicht-in-produktion"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 Tage

    # Datenbank – SQLite lokal, per DATABASE_URL auf Postgres umstellbar
    database_url: str = "sqlite:///./schrittweise.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Magic-Link
    # Sicherer Default: AUS. Lokal aktiviert die .env (aus .env.example) den Dev-Modus;
    # in Produktion muss er bewusst gesetzt werden – sonst kein Login-Link-Leak.
    magic_link_dev_return: bool = False
    # Bewusste Freigabe, den Dev-Login AUSNAHMSWEISE in Produktion zu erlauben
    # (z.B. Test-Deploy vor SMTP-Einrichtung). Ohne dieses Flag verweigert die App
    # in Produktion den Start mit aktivem Dev-Login.
    allow_insecure_dev_login: bool = False
    frontend_base_url: str = "http://localhost:5173"

    # Supabase Auth: Login-Mails über Supabase statt eigenem SMTP (optional).
    # Beide Werte gesetzt -> Magic-Link-Mails verschickt Supabase.
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # SMTP (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Schrittweise <no-reply@schrittweise.ch>"

    # Kontingent
    free_monthly_quota: int = 5

    # Umrechnungskurs fuer die Kosten-Anzeige im Admin-Bereich (Anthropic
    # rechnet in USD ab, der Betreiber denkt in CHF/Rappen)
    usd_chf_rate: float = 0.90

    # Stripe (Token-Paket-Kauf); beide leer = Zahlung deaktiviert
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    @property
    def payments_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)

    # Upload-Verzeichnis (leer = backend/uploads; auf Serverless z.B. /tmp/uploads)
    upload_dir: str = ""

    @property
    def is_production(self) -> bool:
        """True auf Serverless-/Hosting-Plattformen (Vercel, Render)."""
        import os

        return bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))

    @property
    def jwt_secret_is_placeholder(self) -> bool:
        return self.jwt_secret.startswith(("dev-secret", "change-me"))

    @property
    def upload_path(self) -> Path:
        if self.upload_dir:
            return Path(self.upload_dir)
        return Path(__file__).resolve().parent.parent / "uploads"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def supabase_auth_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
