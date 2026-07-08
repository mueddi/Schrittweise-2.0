"""Lokale Zeitzone fuer Wochen-/Monatsgrenzen (Schweiz).

Attempts werden in UTC gespeichert; fuer «diese Woche»/«dieser Monat» aus
Schuelersicht rechnen wir in Europe/Zurich, damit ein Montag 00:30 Lokalzeit
nicht faelschlich zur Vorwoche zaehlt.
"""
from __future__ import annotations

from datetime import timezone, timedelta

try:
    from zoneinfo import ZoneInfo

    LOCAL_TZ = ZoneInfo("Europe/Zurich")
except Exception:  # pragma: no cover – ohne tzdata: fester MEZ-Offset als Fallback
    LOCAL_TZ = timezone(timedelta(hours=1))
