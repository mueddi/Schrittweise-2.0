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


class MathpixOcr:  # pragma: no cover – Platzhalter fuer spaeteren Wechsel
    name = "mathpix"

    def recognize(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError("Mathpix noch nicht angebunden")


def get_ocr_provider() -> OcrProvider:
    return PytesseractOcr()
