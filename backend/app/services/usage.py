"""Erfassung des Anthropic-Token-Verbrauchs fuer die Admin-Kostenauswertung.

Jede echte API-Antwort traegt ein ``usage``-Objekt (input_tokens,
output_tokens, cache_creation_input_tokens, cache_read_input_tokens).
``record`` rechnet daraus die Kosten in USD und legt eine ApiUsage-Zeile ab.
Kosten-Logging darf NIE einen Nutzer-Request killen – record faengt alles ab.
"""
from __future__ import annotations

import logging
import math

log = logging.getLogger("schrittweise.usage")

# Preise in USD pro Million Tokens (input, output) – Stand September 2026,
# platform.claude.com/docs. Cache-Lesen kostet 0.1x des Input-Preises,
# Cache-Schreiben mit 5-Minuten-Frist 1.25x, mit 1-Stunden-Frist 2x.
# (Sonnet 5 hatte bis 31.08.2026 einen Einfuehrungspreis von 2/10 USD –
# Zeilen aus dieser Zeit sind hier mit 3/15 bewertet, also eher zu hoch.)
PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-6": (5.00, 25.00),
}
CACHE_READ_FACTOR = 0.10
CACHE_WRITE_FACTOR = 1.25       # Cache mit 5-Minuten-Frist
CACHE_WRITE_1H_FACTOR = 2.00    # Cache mit 1-Stunden-Frist (Tutor-Prompt + Aufgabe)
# Fallback, falls ein Modellname nicht in der Tabelle steht: lieber leicht
# ueberschaetzen (Sonnet-Preis) als Kosten verschlucken.
_FALLBACK = (3.00, 15.00)


def _rates(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for known, rates in PRICES_USD_PER_MTOK.items():
        if m.startswith(known):
            return rates
    if "haiku" in m:
        return (1.00, 5.00)
    if "opus" in m:
        return (5.00, 25.00)
    if "sonnet" in m:
        return (3.00, 15.00)
    return _FALLBACK


def _tok(usage, field: str) -> int:
    """Liest ein Token-Feld aus dem SDK-Usage-Objekt ODER einem dict."""
    if usage is None:
        return 0
    if isinstance(usage, dict):
        value = usage.get(field, 0)
    else:
        value = getattr(usage, field, 0)
    return int(value or 0)


def cache_write_split(usage) -> tuple[int, int]:
    """Geschriebene Cache-Tokens getrennt nach Frist: (5 Minuten, 1 Stunde).

    Die API liefert die Aufteilung unter ``usage.cache_creation`` als
    ``ephemeral_5m_input_tokens`` / ``ephemeral_1h_input_tokens``. Das SDK
    kennt das Feld als Zusatz (extra="allow"); fehlt es ganz, gilt alles als
    5-Minuten-Schreiben – der Fall vor dem 1h-Cache und bei Antworten ohne
    Aufteilung. Gerechnet wird mit dem Gesamtwert als Obergrenze: der ist
    verlaesslich, die Aufteilung nur eine Verfeinerung.
    """
    gesamt = _tok(usage, "cache_creation_input_tokens")
    if gesamt <= 0:
        return 0, 0
    detail = usage.get("cache_creation") if isinstance(usage, dict) else getattr(usage, "cache_creation", None)
    if detail is None:
        return gesamt, 0
    eine_stunde = min(gesamt, max(0, _tok(detail, "ephemeral_1h_input_tokens")))
    return gesamt - eine_stunde, eine_stunde


def kosten_anteile(model: str, input_t: int, output_t: int, cache_read: int,
                   cache_write_5m: int, cache_write_1h: int) -> dict[str, float]:
    """Die vier Kostenbestandteile eines Aufrufs (oder einer Summe) in USD.

    Eine Funktion fuer beide Wege – die Erfassung (cost_usd) und die
    Auswertung im Admin-Bereich rechnen damit garantiert gleich.
    """
    in_rate, out_rate = _rates(model)
    return {
        "eingabe": input_t * in_rate / 1_000_000,
        "cache_lesen": cache_read * in_rate * CACHE_READ_FACTOR / 1_000_000,
        "cache_schreiben": (cache_write_5m * CACHE_WRITE_FACTOR
                            + cache_write_1h * CACHE_WRITE_1H_FACTOR) * in_rate / 1_000_000,
        "ausgabe": output_t * out_rate / 1_000_000,
    }


def cost_usd(model: str, usage) -> float:
    """Kosten eines Aufrufs in USD aus Modellname + Usage-Objekt/dict."""
    write_5m, write_1h = cache_write_split(usage)
    anteile = kosten_anteile(model, _tok(usage, "input_tokens"), _tok(usage, "output_tokens"),
                             _tok(usage, "cache_read_input_tokens"), write_5m, write_1h)
    return sum(anteile.values())


def charged_tokens(usd: float) -> int:
    """Verrechnete Tokens (1 Token = 1 Rappen) fuer einen Aufruf.

    Echte Kosten in CHF-Rappen mal Sicherheitsmarge, aufgerundet, mindestens 1.
    round(…, 6) vor ceil verhindert Float-Artefakte (6.0000000001 -> 7).
    """
    from ..config import settings

    rappen = usd * settings.usd_chf_rate * 100 * settings.billing_margin
    return max(1, math.ceil(round(rappen, 6)))


def record(db, kind: str, model: str, usage,
           user_id: int | None = None, exercise_id: int | None = None,
           charged: int = 0) -> None:
    """Schreibt eine ApiUsage-Zeile in die uebergebene Session (ohne commit).

    ``charged``: dem Nutzer verrechnete Tokens (0 = gratis, z.B. KI-Suche
    oder unbegrenzte Konten). Der Aufrufer committet zusammen mit seinen
    eigenen Daten. Fehler werden nur geloggt – die Kostenerfassung darf
    keinen Request scheitern lassen.
    """
    try:
        if usage is None or not model:
            return
        from ..models import ApiUsage

        _, write_1h = cache_write_split(usage)
        db.add(ApiUsage(
            user_id=user_id,
            exercise_id=exercise_id,
            kind=kind,
            model=model,
            input_tokens=_tok(usage, "input_tokens"),
            output_tokens=_tok(usage, "output_tokens"),
            cache_read_tokens=_tok(usage, "cache_read_input_tokens"),
            cache_write_tokens=_tok(usage, "cache_creation_input_tokens"),
            cache_write_1h_tokens=write_1h,
            cost_usd=cost_usd(model, usage),
            charged_tokens=charged,
        ))
    except Exception:
        log.exception("Kostenerfassung fehlgeschlagen (kind=%s, model=%s)", kind, model)
