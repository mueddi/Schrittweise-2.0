"""Login-Mails via Supabase Auth (Magic Link), ohne eigenen SMTP-Zugang.

Supabase verschickt die Login-E-Mail über seine Auth-Infrastruktur. Der Link
in der Mail führt (nach Supabase-Verifikation) zurück auf
{FRONTEND_BASE_URL}/login/verify mit einem Supabase-Access-Token im
URL-Fragment; das Backend tauscht dieses Token gegen das eigene App-JWT
(siehe /api/auth/verify-supabase). Nutzerverwaltung und Rollen bleiben
vollständig in der eigenen users-Tabelle.
"""
import logging

import httpx

from ..config import settings

log = logging.getLogger("schrittweise.supabase")


class SupabaseRateLimited(Exception):
    """Supabase hat den Mailversand wegen Rate-Limit abgelehnt (HTTP 429)."""


class SupabaseMailFailed(Exception):
    """Supabase konnte die Mail nicht verschicken – mit Klartext-Grund.

    ``reason`` ist fuer den Betreiber gedacht (Admin-Seite/Alarm-Mail), nicht
    fuer den Nutzer: Ohne diesen Text sieht man nur «Mailversand momentan nicht
    moeglich» und muss im Supabase-Log graben.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def send_magic_link_via_supabase(email: str, redirect_to: str) -> bool:
    """Löst den Versand der Login-Mail durch Supabase Auth aus."""
    if not settings.supabase_auth_enabled:
        return False
    try:
        resp = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/otp",
            params={"redirect_to": redirect_to},
            json={"email": email, "create_user": True},
            headers={"apikey": settings.supabase_anon_key},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        log.error("Supabase nicht erreichbar: %s", exc)
        raise SupabaseMailFailed(f"Supabase nicht erreichbar ({type(exc).__name__}).") from exc
    if resp.status_code == 429:
        raise SupabaseRateLimited()
    if resp.status_code >= 400:
        # Fehlerdetails ins Log – die Nutzerantwort bleibt bewusst generisch.
        log.error(
            "Supabase-OTP fehlgeschlagen: HTTP %s – %s", resp.status_code, resp.text[:500]
        )
        raise SupabaseMailFailed(_reason(resp))
    return True


def _reason(resp: httpx.Response) -> str:
    """Kurzer Klartext-Grund aus der Supabase-Antwort für den Betreiber."""
    msg = ""
    try:
        body = resp.json()
        if isinstance(body, dict):
            msg = str(body.get("msg") or body.get("error_description") or body.get("error") or "")
    except Exception:
        pass
    if not msg:
        msg = resp.text[:200]
    hint = ""
    if resp.status_code >= 500 and "email" in msg.lower():
        # Der echte SMTP-Code (z.B. 525 Unauthorized IP) steht nur im
        # Supabase-Auth-Log – dorthin zeigen statt raten.
        hint = (" Ursache steht im Supabase-Log unter Logs → Auth"
                " (häufig: SMTP-Zugang, gesperrte IP oder nicht verifizierter Absender).")
    return f"Supabase-Mailversand HTTP {resp.status_code}: {msg}{hint}"


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
