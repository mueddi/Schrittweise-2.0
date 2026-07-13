"""OCR hinter einem Interface (OcrProvider).

Vorerst pytesseract; spaeter z.B. Mathpix – nur diese Datei tauschen. Faellt
tesseract aus (nicht installiert), degradiert es sauber: der Preview im
Frontend erlaubt ohnehin die manuelle Korrektur des erkannten Ausdrucks.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Protocol

from ..schemas import OcrResult

log = logging.getLogger("schrittweise.ocr")


class OcrUnavailable(Exception):
    """Erkennung momentan nicht möglich (API-Fehler) – Aufrufer meldet es ehrlich."""


class OcrProvider(Protocol):
    name: str

    def recognize(self, image_bytes: bytes) -> OcrResult: ...


def _guess_math_expression(text: str) -> str | None:
    """Zieht einen plausiblen Mathe-Ausdruck (mit '=') aus erkanntem Text."""
    flat = text.replace("\n", " ").replace("×", "*").replace("·", "*").replace("÷", "/")
    # Zeile/Fragment mit Ziffern, Variable und Gleichheitszeichen
    m = re.search(r"[0-9a-zA-Z][0-9a-zA-Z\s\+\-\*/\^\.\(\)]*=[\s]*[-+]?[0-9a-zA-Z][0-9a-zA-Z\s\+\-\*/\^\.\(\)]*", flat)
    if m:
        return re.sub(r"\s+", "", m.group(0))
    return None


class PytesseractOcr:
    name = "pytesseract"

    def recognize(self, image_bytes: bytes) -> OcrResult:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img, config="--psm 6")
            text = text.strip()
            expr = _guess_math_expression(text)
            conf = 0.7 if expr else (0.4 if text else 0.0)
            return OcrResult(text=text, math_expression=expr, confidence=conf)
        except Exception:
            # tesseract fehlt oder Bild nicht lesbar -> leer, manueller Fallback im UI
            return OcrResult(text="", math_expression=None, confidence=0.0)


class ClaudeVisionOcr:
    """Erkennung über Claude Vision – liest auch Handschrift (Stift-Eingabe) zuverlässig."""

    name = "claude-vision"

    def __init__(self) -> None:
        # nach recognize(): {"model": ..., "usage": ...} fuer die Kostenerfassung
        self.last_usage: dict | None = None

    def recognize(self, image_bytes: bytes) -> OcrResult:
        self.last_usage = None
        try:
            import base64

            import anthropic
            from PIL import Image

            from ..config import settings

            fmt = (Image.open(io.BytesIO(image_bytes)).format or "PNG").lower()
            media_type = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
                fmt, "image/png"
            )
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            # Bewusst das staerkere Modell: Handschrift-Erkennung ist die
            # Kernfunktion der App – Erkennungsqualitaet schlaegt hier Kosten.
            resp = client.messages.create(
                model=settings.anthropic_model_smart,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64.standard_b64encode(image_bytes).decode(),
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Auf dem Bild steht eine handgeschriebene Mathe-Notiz einer "
                                    "Schuelerin/eines Schuelers (12-15 Jahre, Stift auf Tablet oder "
                                    "Papier). Die Schrift kann krakelig, schraeg oder mehrzeilig sein. "
                                    "Transkribiere ALLES, was geschrieben steht, vollstaendig und in "
                                    "der Original-Reihenfolge (jede Zeile der Rechnung als eigene "
                                    "Zeile). Formeln linear schreiben: Brueche als a/b, Potenzen als "
                                    "x^2, Mal als *, Wurzel als sqrt(...). Beispiel: aus zwei "
                                    "handschriftlichen Zeilen wird\n3x + 5 = 20\n3x = 15\n"
                                    "Verwechsle nicht: 1 vs 7, x vs *, 6 vs b, 2 vs z. Wenn ein "
                                    "Zeichen unsicher ist, waehle die in einer Schulrechnung "
                                    "plausibelste Lesart. Gib NUR die Transkription zurueck, ohne "
                                    "Kommentar oder Einleitung. Wenn wirklich nichts lesbar ist, "
                                    "gib exakt LEER zurueck."
                                ),
                            },
                        ],
                    }
                ],
            )
            self.last_usage = {"model": settings.anthropic_model_smart, "usage": resp.usage}
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text.upper() == "LEER":
                text = ""
            expr = _guess_math_expression(text)
            return OcrResult(text=text, math_expression=expr, confidence=0.9 if text else 0.0)
        except Exception as exc:
            # KEIN stiller pytesseract-Fallback mehr: der kann Handschrift nicht
            # und ist auf dem Server gar nicht installiert – das ergab "Konnte
            # nichts erkennen" ohne echten Grund. Ehrlich melden statt raten.
            log.exception("Claude-Vision-Erkennung fehlgeschlagen")
            from . import alert

            alert.notify("ocr", f"{type(exc).__name__}: {exc}")
            raise OcrUnavailable()


class MathpixOcr:  # pragma: no cover – Platzhalter fuer spaeteren Wechsel
    name = "mathpix"

    def recognize(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError("Mathpix noch nicht angebunden")


def get_ocr_provider() -> OcrProvider:
    from ..config import settings

    if settings.anthropic_api_key:
        return ClaudeVisionOcr()
    return PytesseractOcr()
