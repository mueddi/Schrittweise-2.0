"""Erfassung des Anthropic-Token-Verbrauchs fuer die Admin-Kostenauswertung.

Jede echte API-Antwort traegt ein ``usage``-Objekt (input_tokens,
output_tokens, cache_creation_input_tokens, cache_read_input_tokens).
``record`` rechnet daraus die Kosten in USD und legt eine ApiUsage-Zeile ab.
Kosten-Logging darf NIE einen Nutzer-Request killen – record faengt alles ab.
"""
from __future__ import annotations

import logging

log = logging.getLogger("schrittweise.usage")

# Preise in USD pro Million Tokens (input, output) – Stand Juli 2026,
# platform.claude.com/docs. Cache-Lesen kostet 0.1x des Input-Preises,
# Cache-Schreiben (5-Min-TTL) 1.25x.
PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-6": (5.00, 25.00),
}
CACHE_READ_FACTOR = 0.10
CACHE_WRITE_FACTOR = 1.25
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


def cost_usd(model: str, usage) -> float:
    """Kosten eines Aufrufs in USD aus Modellname + Usage-Objekt/dict."""
    in_rate, out_rate = _rates(model)
    input_t = _tok(usage, "input_tokens")
    output_t = _tok(usage, "output_tokens")
    cache_read = _tok(usage, "cache_read_input_tokens")
    cache_write = _tok(usage, "cache_creation_input_tokens")
    usd = (
        input_t * in_rate
        + output_t * out_rate
        + cache_read * in_rate * CACHE_READ_FACTOR
        + cache_write * in_rate * CACHE_WRITE_FACTOR
    ) / 1_000_000
    return usd


def record(db, kind: str, model: str, usage,
           user_id: int | None = None, exercise_id: int | None = None) -> None:
    """Schreibt eine ApiUsage-Zeile in die uebergebene Session (ohne commit).

    Der Aufrufer committet zusammen mit seinen eigenen Daten. Fehler werden
    nur geloggt – die Kostenerfassung darf keinen Request scheitern lassen.
    """
    try:
        if usage is None or not model:
            return
        from ..models import ApiUsage

        db.add(ApiUsage(
            user_id=user_id,
            exercise_id=exercise_id,
            kind=kind,
            model=model,
            input_tokens=_tok(usage, "input_tokens"),
            output_tokens=_tok(usage, "output_tokens"),
            cache_read_tokens=_tok(usage, "cache_read_input_tokens"),
            cache_write_tokens=_tok(usage, "cache_creation_input_tokens"),
            cost_usd=cost_usd(model, usage),
        ))
    except Exception:
        log.exception("Kostenerfassung fehlgeschlagen (kind=%s, model=%s)", kind, model)
