"""KI-Suche für die Aufgaben-Bibliothek.

Der Betreiber beschreibt jedes Dokument; die Suche schickt Anfrage +
kompakte Metadaten an ein kleines Claude-Modell, das die passenden
Dokument-IDs gerankt zurückgibt. Ohne API-Key oder bei jedem Fehler gibt
``rank_documents`` None zurück und der Router fällt auf ILIKE zurück.
"""
from __future__ import annotations

import json
import logging

from ..config import settings

log = logging.getLogger("schrittweise.library")

MAX_CANDIDATES = 100
MAX_RESULTS = 20
DESC_CHARS = 300


def rank_documents(q: str, docs: list[dict], usage_out: dict | None = None) -> list[int] | None:
    """Gerankte Dokument-IDs zur Suchanfrage; None => Aufrufer nutzt ILIKE-Fallback.

    ``usage_out``: optionales dict, das mit ``model`` und ``usage`` der
    API-Antwort gefuellt wird (Kostenerfassung)."""
    if not settings.anthropic_api_key or not docs:
        return None
    try:
        import anthropic

        candidates = [
            {
                "id": d["id"],
                "titel": d["title"],
                "beschreibung": (d["description"] or "")[:DESC_CHARS],
                "kategorie": d["category"],
                "stufen": d["grade_levels"],
                "schwierigkeit": d["difficulty"],
            }
            for d in docs[:MAX_CANDIDATES]
        ]
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.anthropic_model_default,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Du bist die Suchfunktion einer Mathematik-Aufgabenbibliothek "
                        "(Oberstufe & Gymnasium, Schweiz).\n"
                        f"Suchanfrage: «{q}»\n"
                        f"Dokumente: {json.dumps(candidates, ensure_ascii=False)}\n\n"
                        "Gib NUR ein JSON-Array der IDs der inhaltlich passenden Dokumente "
                        f"zurück, beste Treffer zuerst, maximal {MAX_RESULTS}. "
                        "Beispiel: [3,1]. Wenn nichts passt: []"
                    ),
                }
            ],
        )
        if usage_out is not None:
            usage_out["model"] = settings.anthropic_model_default
            usage_out["usage"] = resp.usage
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ranked = json.loads(raw)
        valid = {c["id"] for c in candidates}
        result = [int(i) for i in ranked if int(i) in valid]
        return result[:MAX_RESULTS]
    except Exception:
        log.exception("KI-Suche fehlgeschlagen – ILIKE-Fallback")
        return None
