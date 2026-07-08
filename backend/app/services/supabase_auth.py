"""Login-Mails via Supabase Auth (Magic Link), ohne eigenen SMTP-Zugang.

Supabase verschickt die Login-E-Mail über seine Auth-Infrastruktur. Der Link
in der Mail führt (nach Supabase-Verifikation) zurück auf
{FRONTEND_BASE_URL}/login/verify mit einem Supabase-Access-Token im
URL-Fragment; das Backend tauscht dieses Token gegen das eigene App-JWT
(siehe /api/auth/verify-supabase). Nutzerverwaltung und Rollen bleiben
vollständig in der eigenen users-Tabelle.
"""
import httpx

from ..config import settings


class SupabaseRateLimited(Exception):
    """Supabase hat den Mailversand wegen Rate-Limit abgelehnt (HTTP 429)."""


def send_magic_link_via_supabase(email: str, redirect_to: str) -> bool:
    """Löst den Versand der Login-Mail durch Supabase Auth aus."""
    if not settings.supabase_auth_enabled:
        return False
    resp = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/otp",
        params={"redirect_to": redirect_to},
        json={"email": email, "create_user": True},
        headers={"apikey": settings.supabase_anon_key},
        timeout=15,
    )
    if resp.status_code == 429:
        raise SupabaseRateLimited()
    resp.raise_for_status()
    return True


def get_verified_email(access_token: str) -> str | None:
    """Validiert ein Supabase-Access-Token serverseitig und gibt die E-Mail zurück.

    Die Prüfung läuft gegen /auth/v1/user (kein lokales JWT-Decoding nötig,
    funktioniert damit auch nach Key-Rotation bei Supabase).
    """
    if not settings.supabase_auth_enabled or not access_token:
        return None
    try:
        resp = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=15,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    email = (resp.json().get("email") or "").lower().strip()
    return email or None
