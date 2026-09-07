"""Wie lang ist der System-Prompt des Tutors – und cacht Haiku ihn ueberhaupt?

Claude Haiku 4.5 legt erst ab 4096 Token Praefix einen Cache an; darunter
passiert stumm nichts, und jeder Turn zahlt den vollen Eingabepreis. Sonnet
cacht ab 1024. Dieses Skript zaehlt den gecachten Praefix (System-Prompt) und
sagt, ob die Schwelle erreicht ist. Vor jeder Kuerzung des Prompts laufen
lassen.

    cd backend && python scripts/pruefe_prompt_tokens.py

Mit gesetztem ANTHROPIC_API_KEY zaehlt die API exakt (kostenlos); ohne
Schluessel wird grob geschaetzt (ein Token ≈ 3.5 Zeichen deutscher Text).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.tutor import SYSTEM_BLOCKS, SYSTEM_PROMPT  # noqa: E402

SCHWELLEN = {"claude-haiku-4-5": 4096, "claude-sonnet-5": 1024}


def zaehle(model: str) -> tuple[int, str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic

            antwort = anthropic.Anthropic(api_key=key).messages.count_tokens(
                model=model, system=SYSTEM_BLOCKS,
                messages=[{"role": "user", "content": "x"}])
            return antwort.input_tokens, "gezaehlt von der API"
        except Exception as exc:  # pragma: no cover - Netz/Key-Probleme
            print(f"  (API-Zaehlung fehlgeschlagen: {type(exc).__name__}; schaetze)")
    return round(len(SYSTEM_PROMPT) / 3.5), "geschaetzt"


def main() -> int:
    print(f"System-Prompt: {len(SYSTEM_PROMPT)} Zeichen")
    ok = True
    for model, schwelle in SCHWELLEN.items():
        tokens, art = zaehle(model)
        reicht = tokens >= schwelle
        ok = ok and reicht
        print(f"  {model}: {tokens} Token ({art}) – Cache-Schwelle {schwelle}: "
              f"{'erreicht' if reicht else 'NICHT erreicht, wird nicht gecacht'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
