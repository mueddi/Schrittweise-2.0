"""Mailversand fuer den Magic-Link.

Ohne SMTP-Konfiguration wird nichts verschickt – der Aufrufer gibt den Link im
Dev-Modus stattdessen direkt zurueck. So laeuft die App auf Render free tier
ohne Mailserver, und ein echter Provider ist spaeter reine Config.
"""
import smtplib
from email.message import EmailMessage

from ..config import settings


def send_magic_link(to_email: str, link: str) -> bool:
    if not settings.smtp_enabled:
        return False
    msg = EmailMessage()
    msg["Subject"] = "Dein Login-Link für Schrittweise"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Hoi!\n\nHier ist dein Login-Link – gültig für kurze Zeit:\n{link}\n\n"
        "Wenn du das nicht warst, kannst du diese Mail ignorieren.\n\nSchrittweise"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)
    return True
