"""OCR hinter einem Interface (OcrProvider).

Vorerst pytesseract; spaeter z.B. Mathpix – nur diese Datei tauschen. Faellt
tesseract aus (nicht installiert), degradiert es sauber: der Preview im
Frontend erlaubt ohnehin die manuelle Korrektur des erkannten Ausdrucks.
"""
from __future__ import annotations

import io
import re
from typing import Protocol

from ..schemas import OcrResult


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

    def recognize(self, image_bytes: bytes) -> OcrResult:
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
            resp = client.messages.create(
                model=settings.anthropic_model_default,
                max_tokens=300,
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
                                    "Transkribiere die (hand)geschriebene Mathe-Notiz auf dem Bild "
                                    "als reinen Text. Formeln linear schreiben (z.B. 3x + 5 = 20, "
                                    "Brueche als a/b, Potenzen als ^). Gib NUR die Transkription "
                                    "zurueck, ohne Kommentar. Wenn nichts lesbar ist, gib LEER zurueck."
                                ),
                            },
                        ],
                    }
                ],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text.upper() == "LEER":
                text = ""
            expr = _guess_math_expression(text)
            return OcrResult(text=text, math_expression=expr, confidence=0.9 if text else 0.0)
        except Exception:
            # Vision nicht verfuegbar/fehlgeschlagen -> klassisches OCR als Fallback
            return PytesseractOcr().recognize(image_bytes)


class MathpixOcr:  # pragma: no cover – Platzhalter fuer spaeteren Wechsel
    name = "mathpix"

    def recognize(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError("Mathpix noch nicht angebunden")


def get_ocr_provider() -> OcrProvider:
    from ..config import settings

    if settings.anthropic_api_key:
        return ClaudeVisionOcr()
    return PytesseractOcr()
