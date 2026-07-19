"""Zweisprachige Nutzertexte (Deutsch/Englisch) fuer Backend-Meldungen.

Kein Key-Woerterbuch: jede Stelle uebergibt beide Fassungen direkt –
``t(lang, "Deutsch …", "English …")``. Das haelt Text und Verwendung
beieinander und kann nicht auseinanderlaufen.
"""
from __future__ import annotations


def norm(lang: str | None) -> str:
    """Normalisiert eine Sprachangabe auf 'de' oder 'en' (Default 'de')."""
    return "en" if (lang or "").strip().lower().startswith("en") else "de"


def t(lang: str | None, de: str, en: str) -> str:
    return en if norm(lang) == "en" else de


def lang_of(user=None, request=None) -> str:
    """Sprache eines Requests: eingeloggtes Profil vor X-Lang-Header vor 'de'."""
    if user is not None and getattr(user, "language", None):
        return norm(user.language)
    if request is not None:
        header = request.headers.get("x-lang")
        if header:
            return norm(header)
    return "de"
