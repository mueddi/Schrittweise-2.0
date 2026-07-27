"""Probeprüfung zu einem Thema: erzeugen und korrigieren.

Zwei Entscheidungen prägen diesen Dienst:

1. **Korrigiert wird mit SymPy, nicht mit der KI.** Das Modell liefert zu jeder
   Aufgabe einen Prüfausdruck mit; ``sympy_verifier.verify`` bewertet die
   Antwort dann deterministisch und gratis. Nur Aufgaben ohne brauchbaren
   Ausdruck müssen überhaupt an ein Modell. Das ist billiger *und*
   verlässlicher als eine KI-Bewertung.

2. **Ein einziger Modellaufruf** erzeugt die ganze Prüfung. Ein Aufruf pro
   Aufgabe wäre das Sechsfache an Kosten und sechs Ausfallstellen statt einer.
"""
from __future__ import annotations

import json
import logging

from ..config import settings
from .sympy_verifier import extract_expression

log = logging.getLogger("schrittweise.exam")

try:
    import anthropic
except Exception:  # pragma: no cover – Paket fehlt nur in Minimal-Installationen
    anthropic = None

AUFGABEN_ZIEL = 8      # so viele Aufgaben werden angefragt
AUFGABEN_MIN = 3       # darunter ist es keine Prüfung
MAX_TOKENS = 2000
# Zeitlimit unter dem Deckel der Hosting-Plattform (Vercel bricht nach 60 s ab),
# damit die App den Ausfall selbst bemerkt statt abgeschossen zu werden.
CLIENT_TIMEOUT = 30.0

# Geschätzte Kosten in Rappen, die dem Schüler VOR dem Start gezeigt werden.
# Bewusst der obere Wert: eine Überraschung nach unten ist harmlos, eine nach
# oben nicht. Grundlage: ~1500 Eingabe + ~1300 Ausgabe auf Sonnet, Marge x3.
KOSTEN_SCHAETZUNG_RAPPEN = 8


def _ziele(text: str) -> list[str]:
    return [z.strip() for z in (text or "").splitlines() if z.strip()][:12]


def kosten_schaetzung() -> int:
    return KOSTEN_SCHAETZUNG_RAPPEN


def _prompt(thema: str, ziele: list[str], aufgaben: list[str], stufe: str | None) -> str:
    vorhandene = "\n".join(f"- {a}" for a in aufgaben[:12]) or "(keine)"
    ziel_liste = "\n".join(f"- {z}" for z in ziele)
    return (
        "Du erstellst eine kurze Mathematik-Probeprüfung für eine Schweizer "
        f"Schülerin oder einen Schüler ({stufe or 'Oberstufe'}, Lehrplan 21).\n\n"
        f"THEMA: {thema}\n\n"
        f"LERNZIELE (jede Aufgabe muss genau EINES davon prüfen):\n{ziel_liste}\n\n"
        "AUFGABEN, DIE IM UNTERRICHT SCHON GESTELLT WURDEN – dieselbe Art und "
        f"derselbe Schwierigkeitsgrad, aber ANDERE Zahlen:\n{vorhandene}\n\n"
        f"Erzeuge genau {AUFGABEN_ZIEL} Aufgaben, aufsteigend nach Schwierigkeit. "
        "Gib NUR ein JSON-Array zurück, ohne Text davor oder danach. Jedes Element:\n"
        '{"frage": "...", "ausdruck": "...", "ziel": "..."}\n\n'
        "- «frage»: die Aufgabenstellung, wie sie auf einem Prüfungsblatt steht. "
        "Kurz und eindeutig. Keine Lösung, kein Hinweis.\n"
        "- «ausdruck»: dieselbe Aufgabe in EINER maschinell lösbaren Zeile, z.B. "
        '"3x + 5 = 20" oder "348 + 267". Nur eine Unbekannte, und sie muss zu '
        "einer ZAHL auflösen. Ist das nicht möglich (z.B. Zeichnen, Begründen), "
        'dann "" (leerer String) – dann wird von Hand korrigiert.\n'
        "- «ziel»: wörtlich eines der Lernziele oben.\n"
    )


def _saeubere(rohtext: str) -> list[dict]:
    """JSON aus der Modellantwort ziehen und jede Aufgabe prüfen.

    Der Prüfausdruck wird NICHT geglaubt, sondern mit ``extract_expression``
    nachgerechnet: nur was sich zu einer Zahl auflöst, wird gespeichert. Sonst
    landete – wie schon einmal – ein unbrauchbarer Ausdruck als «Aufgabe» in
    der Datenbank und die richtige Antwort gälte danach als falsch.
    """
    raw = rohtext.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not raw.startswith("["):
        # Modell hat doch etwas drumherum geschrieben: das Array herausfischen
        a, b = raw.find("["), raw.rfind("]")
        if a == -1 or b <= a:
            raise ValueError("keine JSON-Liste in der Antwort")
        raw = raw[a:b + 1]
    daten = json.loads(raw)
    if not isinstance(daten, list):
        raise ValueError("JSON ist keine Liste")

    aufgaben: list[dict] = []
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            continue
        frage = str(eintrag.get("frage") or "").strip()
        if not frage:
            continue
        ausdruck = str(eintrag.get("ausdruck") or "").strip()
        geprueft = ""
        if ausdruck:
            # Der Türsteher: liefert None, wenn der Ausdruck nicht zu einer
            # Zahl auflöst. Dann korrigiert lieber ein Mensch/das Modell.
            gewonnen = extract_expression(ausdruck)
            if gewonnen:
                geprueft = gewonnen[:255]
        aufgaben.append({
            "frage": frage[:2000],
            "math_expression": geprueft,
            "goal": str(eintrag.get("ziel") or "").strip()[:200],
        })
    return aufgaben


def erzeuge(thema: str, learning_goals: str, aufgaben_texte: list[str],
            grade_level: str | None, usage_out: dict | None = None) -> list[dict]:
    """Erzeugt die Prüfungsaufgaben. Wirft, wenn nichts Brauchbares herauskommt.

    Der Aufrufer darf erst abbuchen und speichern, wenn das hier durchläuft –
    eine halbe Prüfung ist nichts wert und darf nichts kosten.
    """
    ziele = _ziele(learning_goals)
    if not ziele:
        raise ValueError("keine Lernziele")
    if not (settings.anthropic_api_key and anthropic):
        raise RuntimeError("KI nicht konfiguriert")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                 timeout=CLIENT_TIMEOUT, max_retries=1)
    prompt = _prompt(thema, ziele, aufgaben_texte, grade_level)

    # Dieselbe Ausweich-Kette wie im Chat: eine Prüfung darf nicht an einem
    # ueberlasteten Modell scheitern.
    from .tutor import _modell_kette

    letzter: Exception | None = None
    for modell in _modell_kette(settings.anthropic_model_smart):
        try:
            resp = client.messages.create(
                model=modell, max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            roh = "".join(b.text for b in resp.content if b.type == "text")
            fertig = _saeubere(roh)
            if len(fertig) < AUFGABEN_MIN:
                raise ValueError(f"nur {len(fertig)} brauchbare Aufgaben")
            if usage_out is not None:
                usage_out["model"] = modell
                usage_out["usage"] = resp.usage
            return fertig[:AUFGABEN_ZIEL]
        except Exception as exc:
            letzter = exc
            log.exception("Pruefungs-Erzeugung mit %s fehlgeschlagen", modell)
    raise RuntimeError(f"Pruefung konnte nicht erzeugt werden: {letzter}")


def note_aus_punkten(richtig: int, total: int) -> float:
    """Punkte-Anteil auf die Schweizer Skala: 0 % -> 1.0, 100 % -> 6.0."""
    if total <= 0:
        return 1.0
    return round(5 * (richtig / total) + 1, 1)
