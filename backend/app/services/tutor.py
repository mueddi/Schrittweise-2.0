"""Tutor-Logik: Hinweis-Leiter-Zustand + Anthropic-Anbindung (Streaming).

Der System-Prompt erzwingt die 4-Stufen-Leiter hart. Das Backend bleibt die
Autorität über den Leiter-Zustand: es berechnet pro Turn, welche Stufe erlaubt
ist, und das LLM formuliert nur die pädagogische Antwort dieser Stufe.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..config import settings
from ..i18n import t
from .sympy_verifier import Verification

log = logging.getLogger("schrittweise.tutor")

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None


# ---- Hinweis-Leiter ----
STUFEN = {
    1: "Aktivierende Frage – stell eine Frage, die zum ersten Schritt hinfuehrt.",
    2: "Kleiner Tipp – gib einen konkreten, aber kleinen Hinweis, ohne zu rechnen.",
    3: "Teilschritt vorgemacht – mach EINEN Rechenschritt vor, aber nicht die ganze Loesung.",
    4: "Volle Loesung – jetzt darfst du den Loesungsweg Schritt fuer Schritt zeigen.",
}

SYSTEM_PROMPT = """Du bist «Schrittweise», ein geduldiger Mathe-Tutor fuer Schweizer Schueler:innen der Oberstufe (Sek I, Lehrplan 21) UND des Gymnasiums (bis zur Matura). Die Regie-Anweisung nennt dir die Klassenstufe: Bei Sek I erklaerst du einfach, kleinschrittig und mit Alltagsbildern. Bei Gymnasium nutzt du praezise Fachsprache und zuegigere Schritte auf Matura-Niveau (Funktionen, Analysis, Vektoren, Stochastik) – aber auch dort gilt die Hinweis-Leiter.

DEINE EISERNE REGEL: Du verraetst die Loesung NIEMALS direkt, ausser die Regie-Anweisung erlaubt ausdruecklich Stufe 4. Du fuehrst ueber eine HINWEIS-LEITER mit vier Stufen zum eigenen Denken:
  Stufe 1 – Aktivierende Frage («Was muesstest du tun, damit die +5 verschwindet?»)
  Stufe 2 – Kleiner Tipp
  Stufe 3 – Ein Teilschritt vorgemacht (aber nicht die ganze Loesung)
  Stufe 4 – Volle Loesung, Schritt fuer Schritt – NUR wenn die Regie sie freigibt (nach mind. 2 echten eigenen Versuchen)

WENN DER SCHUELER BETTELT («gib mir die Loesung 🙏», «sag einfach die Antwort»): Lehne freundlich und bestimmt ab und stell die aktivierende Frage der aktuellen Stufe. Beispiel: «Mach ich extra nicht 🙂 – aber ich helf dir hin. Was faellt dir zuerst auf?» Erhoehe die Stufe dabei NICHT.

STIL:
- Duze, sei ermutigend, nie belehrend. Schweizer Hochdeutsch: schreib «weiss» statt «weiß» – nie den Buchstaben «ß» verwenden.
- Kurz halten (1–3 Saetze). Eine Frage oder ein Hinweis pro Antwort, nicht mehr.
- JEDE Formel, Gleichung oder Rechnung MUSS zwischen Dollarzeichen stehen, auch kurze wie $x = 5$. Ein eigenstaendiger Rechenschritt darf auf eigener Zeile als $$ ... $$ stehen (wird zentriert dargestellt).
- LESART linearer Schreibweisen: von links nach rechts wie im Schulheft – «3/2y» bedeutet $\\frac{3}{2} \\cdot y$, NICHT $\\frac{3}{2y}$. Ist eine Schreibweise mehrdeutig und macht es fuers Ergebnis einen Unterschied, bestaetige zuerst kurz die Lesart.
- Hat die Aufgabe ein BILD (Figur, Skizze, Koordinatensystem): schau es genau an und beziehe dich konkret darauf («die Seite $a$ im Bild», «der rechte Winkel unten links»). Lies Masse und Beschriftungen aus der Figur, wenn sie im Text fehlen. Weicht der transkribierte Aufgabentext vom Bild ab (z.B. falsch gelesener Bruch), ist das BILD massgeblich – korrigiere die Lesart still und rechne mit der Version aus dem Bild.
- FORMAT: schlichter, uebersichtlicher Text. Hoechstens **fett** fuer EIN Schluesselwort pro Antwort. KEIN anderes Markdown: keine Titel (#), keine Tabellen, keine Aufzaehlungen mit * – wenn du aufzaehlst, nutze einen Bindestrich am Zeilenanfang.
- Wenn der Schueler richtig liegt: freu dich echt und bestaetige knapp, warum es stimmt.
- Wenn etwas falsch ist: sag nicht einfach «falsch», sondern frag nach oder zeig, wo es harzt.
- Reagiere IMMER zuerst auf das, was der Schueler TATSAECHLICH geschrieben oder gezeichnet hat – auch wenn es deine Frage nicht beantwortet. Weicht es ab, benenne das kurz und ehrlich («Du hast $5 \\cdot 3$ geschrieben – meine Frage war …»).
- Bestaetige NIE eine Antwort als richtig, die der Schueler so nicht gegeben hat. Bist du unsicher, was gemeint ist, frag nach statt zu raten.
- Haengt an der Schueler-Nachricht eine ZEICHNUNG (Bild), lies sie genau und beziehe dich auf ihren ECHTEN Inhalt – nicht auf das, was du erwartet hast.

SKIZZEN (maechtiges Werkzeug – aber sparsam):
Wenn eine Skizze WIRKLICH beim Verstehen hilft, fuege GENAU EINEN Skizzen-Block ein: der Marker [[FIGUR]], direkt gefolgt von EINEM JSON-Objekt, direkt gefolgt von [[/FIGUR]] – sonst NICHTS im Block. Beispiel einer Antwort mit Skizze:
«Stell dir die Gleichung als Waage vor: [[FIGUR]]{"typ":"waage","links":"3x + 5","rechts":"20"}[[/FIGUR]] Was muesstest du auf BEIDEN Seiten wegnehmen?»
Erlaubte JSON-Objekte:
- {"typ":"bruch","zaehler":3,"nenner":4} – Pizza + Balken fuer Brueche
- {"typ":"zahlenstrahl","von":-5,"bis":5,"punkte":[2,-3]}
- {"typ":"waage","links":"3x + 5","rechts":"20"} – Gleichung als Waage
- {"typ":"rechteck","a":8,"b":5,"flaeche":40} (flaeche optional)
- {"typ":"dreieck","a":3,"b":4,"c":5,"rechtwinklig":true}
- {"typ":"koordinaten","punkte":[[1,2],[3,4]],"gerade":{"m":2,"q":-1}} (gerade optional, Bereich -5..5)
- {"typ":"winkel","grad":35}
- {"typ":"kreis","radius":4} oder {"typ":"kreis","durchmesser":8}
- {"typ":"prozentbalken","prozent":35}
- {"typ":"saeulen","werte":[3,7,5],"labels":["Mo","Di","Mi"]}
- Fuer ALLE anderen Formen (Trapez, Raute, zusammengesetzte Figuren): {"typ":"figur","punkte":[[0,0],[80,0],[60,40],[20,40]],"linien":[[0,1],[1,2],[2,3],[3,0]],"labels":[{"x":40,"y":-8,"text":"a"}]} – Koordinaten frei waehlbar (werden eingepasst); ohne "linien" wird der Punktezug geschlossen gezeichnet.
Zeichne NIEMALS selbst SVG/HTML. Die Skizze ersetzt keine Erklaerung – kurzer Text gehoert immer dazu. Hoechstens eine Skizze pro Antwort, und nur wenn sie wirklich etwas zeigt.

SO ERKLAERST DU (SEHR WICHTIG):
- Die meisten Schueler:innen hier haben Muehe mit Mathe und wenig Selbstvertrauen. Geh IMMER davon aus, dass die Grundlagen wackeln.
- Extrem einfache Sprache: kurze Saetze. Ein Gedanke pro Satz.
- KEIN Fachwort ohne sofortige Alltags-Erklaerung in Klammern, z.B. «Term (= ein Rechenausdruck)», «Variable (= die unbekannte Zahl, hier $x$)».
- Nutze Alltagsbilder: die Waage fuer Gleichungen (beide Seiten gleich schwer halten), die Pizza fuer Brueche, das Sackgeld fuer Prozente.
- Sag NIE «das ist einfach» oder «das ist doch klar» – das beschaemt. Sag stattdessen «das ueben wir kurz zusammen».
- Wenn der Schueler «ich verstehe es nicht» sagt: NICHT dasselbe wiederholen, sondern EINFACHER erklaeren – kleinerer Schritt, konkretes Alltagsbeispiel mit Zahlen.
- Lob konkret statt pauschal: nicht «super!», sondern «stark – das Minusrechnen auf beiden Seiten hat gestimmt».

Du bekommst pro Nachricht eine REGIE-ANWEISUNG mit: erlaubter Stufe, SymPy-Pruefergebnis und Anzahl eigener Versuche. Halte dich strikt daran. Die interne Loesung, falls mitgegeben, verwendest du HOECHSTENS auf Stufe 4."""


# "loesung" (oe), "lösung", "losung" alle abdecken
_LOESUNG = r"l(?:oe|ö|o)sung"
_ZIEL = rf"(?:{_LOESUNG}|antwort|ergebnis|resultat)"
BETTEL_PATTERNS = [
    rf"gib (mir )?die {_LOESUNG}", rf"sag(?:s)? mir die {_LOESUNG}", rf"was ist die {_LOESUNG}",
    r"einfach die antwort", r"sag einfach", r"verrat", rf"{_LOESUNG} bitte", r"nur die antwort",
    r"gib die antwort", r"sag mir das ergebnis", rf"{_LOESUNG}\s*🙏", r"bitte die antwort",
    # generischer: «zeig/nenn/sag mir … Loesung/Antwort/Ergebnis», «wie lautet die Antwort»
    rf"zeig (mir )?(die|den|das)? ?{_ZIEL}", rf"nenn(e)? (mir )?(die|das)? ?{_ZIEL}",
    rf"wie (lautet|heisst|ist) (die|das) {_ZIEL}", rf"sag (mir )?(die|das) {_ZIEL}",
    rf"gib (mir )?(die|das) {_ZIEL}", rf"was ist (die|das) {_ZIEL}", rf"loes(e)? (es |die aufgabe )?fuer mich",
]
# «Ich verstehe es nicht» / «erklär es einfacher»: der Schueler braucht KEINE
# neue Hilfestufe, sondern DIESELBE Erklaerung in einfacheren Worten. Diese
# Muster duerfen die Leiter deshalb NICHT hochtreiben.
SIMPLER_PATTERNS = [
    r"einfacher", r"versteh(e)? ?(es |das |ich )?nicht", r"kapier", r"check(e)? (es |das )?nicht",
    r"nochmal erkl[aä]r", r"erkl[aä]r.{0,20}nochmal", r"zu schwierig", r"zu kompliziert",
    # «Erklaer's anders»-Chips: andere DARSTELLUNG derselben Stufe, kein Stufen-Anstieg
    r"skizze", r"zeichn", r"alltag", r"beispiel aus", r"konkreten zahlen", r"zahlen statt",
]
HILFE_PATTERNS = [
    r"weiss (es )?nicht", r"keine ahnung", r"komm(e)? nicht weiter", r"h[aä]nge", r"h[iä]lfe",
    r"tipp", r"hinweis", r"n[aä]chste stufe",
    r"wie (geht|mach|anfangen|weiter)", r"was (jetzt|nun|soll ich)", r"stecke fest",
]


def detect_intent(message: str, verification: Verification) -> str:
    """'plea' | 'correct' | 'attempt' | 'step' | 'simpler' | 'stuck'.

    'step' = eigener Schritt, der NICHT falsch ist (richtige Umformung oder
    nicht pruefbar): zaehlt als Versuch, treibt die Hilfe-Stufe aber nicht
    hoch – mehr Hilfe gibt es nur bei Fehlern ('attempt') oder auf Anfrage.
    """
    low = message.lower()
    if verification.status == "correct":
        return "correct"
    if any(re.search(p, low) for p in BETTEL_PATTERNS):
        return "plea"
    if verification.status == "partial":
        return "step"
    if verification.status == "incorrect":
        return "attempt"
    if verification.extracted:  # eine Zahl/Antwort war drin, aber nicht pruefbar
        return "step"
    # Fragt nach Loesung/Antwort/Ergebnis OHNE eigenen Rechenversuch -> Betteln,
    # damit «zeig mir die antwort» die Leiter nicht hochtreibt.
    if re.search(_ZIEL, low):
        return "plea"
    if any(re.search(p, low) for p in SIMPLER_PATTERNS):
        return "simpler"
    if any(re.search(p, low) for p in HILFE_PATTERNS):
        return "stuck"
    return "stuck"


@dataclass
class LadderStep:
    intent: str
    allowed_stage: int
    own_attempts: int
    solved: bool
    permit_solution: bool


def advance_ladder(current_stage: int, own_attempts: int, intent: str, min_attempts: int = 2) -> LadderStep:
    """Deterministische Zustandsmaschine der Hinweis-Leiter."""
    solved = intent == "correct"
    if solved:
        return LadderStep(intent, max(current_stage, 1), own_attempts, True, False)

    if intent == "plea":
        # Verdiente Freigabe: wer auf hoher Stufe schon genug eigene Versuche
        # gemacht hat, bekommt die Loesung auf Nachfrage WIRKLICH – sonst
        # waere die Regel «nach 2 Versuchen» nie aktiv nutzbar.
        if current_stage >= 3 and own_attempts >= min_attempts:
            return LadderStep(intent, 4, own_attempts, False, True)
        # Betteln davor: Stufe bleibt, kein Versuch gezaehlt
        stage = max(current_stage, 1)
        return LadderStep(intent, stage, own_attempts, False, False)

    if intent == "simpler":
        # «Verstehe es nicht» / «erklaer einfacher»: dieselbe Stufe, nur in
        # einfacheren Worten – Nachfragen kostet keine Sprosse und keinen Versuch.
        return LadderStep(intent, max(current_stage, 1), own_attempts, False, False)

    if intent == "step":
        # Richtiger (oder nicht pruefbarer) eigener Schritt: zaehlt als Versuch,
        # aber die Hilfe-Stufe bleibt – wer gut unterwegs ist, braucht nicht
        # MEHR Hilfe, sondern nur Bestaetigung und den naechsten Anstoss.
        return LadderStep(intent, max(current_stage, 1), own_attempts + 1, False, False)

    if intent == "attempt":
        own_attempts += 1

    # Mehr Hilfe noetig (Fehler oder Hilfe-Anfrage): eine Sprosse hoeher, Deckel bei 4
    stage = min(max(current_stage, 0) + 1, 4)
    permit = stage >= 4 and own_attempts >= min_attempts
    if stage == 4 and not permit:
        stage = 3  # volle Loesung noch gesperrt -> auf Stufe 3 halten
    return LadderStep(intent, stage, own_attempts, False, permit)


# ---- Modellwahl ----
def pick_model(exercise_text: str, exercise_expr: str | None) -> str:
    """Standard = Haiku; Sonnet nur fuer komplexe Faelle (Textaufgaben/Geometrie)."""
    text = (exercise_text or "").lower()
    complex_markers = ["beweis", "geometrie", "dreieck", "kreis", "winkel", "flaeche", "fläche",
                       "volumen", "textaufgabe", "wenn", "insgesamt", "zusammen", "prozent",
                       # Gymnasial-Stoff gehoert ans starke Modell
                       "funktion", "ableitung", "integral", "vektor", "logarithm",
                       "trigonometrie", "sinus", "cosinus", "tangens", "gleichungssystem",
                       "wahrscheinlichkeit", "grenzwert", "folge"]
    long_wordy = len(text.split()) > 40 and not exercise_expr
    if long_wordy or any(m in text for m in complex_markers):
        return settings.anthropic_model_smart
    return settings.anthropic_model_default


def _regie(step: LadderStep, verification: Verification, exercise_text: str, exercise_expr: str | None,
           grade_level: str | None = None) -> str:
    lines = [
        "REGIE-ANWEISUNG (nicht an den Schueler weitergeben):",
        f"- Aufgabe: {exercise_text}" + (f"  [Ausdruck: {exercise_expr}]" if exercise_expr else ""),
        f"- Erlaubte Stufe: {step.allowed_stage} – {STUFEN[step.allowed_stage]}",
        f"- SymPy-Pruefung der letzten Antwort: {verification.status} ({verification.detail})",
        f"- Bisherige eigene Versuche: {step.own_attempts}",
    ]
    if grade_level:
        g = grade_level.lower()
        if "gym" in g:
            lines.append(f"- Stufe: {grade_level} (Gymnasium/Matura-Niveau) – praezise Fachsprache ist erwuenscht, zuegigere Schritte, keine Baby-Schritte.")
        elif "mittel" in g:
            lines.append(f"- Stufe: {grade_level} (Mittelstufe, ca. 4.-6. Klasse, 10-12 Jahre) – sehr einfache Sprache, ganz kleine Schritte, kleine Zahlen, viele Alltagsbilder; Stoff: Grundoperationen, Brueche, einfache Geometrie. KEINE Fachbegriffe ohne Erklaerung.")
        else:
            lines.append(f"- Stufe: {grade_level} (Oberstufe/Sek I) – einfach erklaeren, kleine Schritte, Alltagsbilder.")
    if verification.status == "unknown":
        lines.append("- Die Antwort konnte NICHT automatisch geprueft werden – beurteile selbst sorgfaeltig, was wirklich dasteht (oder auf der Zeichnung steht); im Zweifel nachfragen statt bestaetigen.")
    if step.intent == "plea" and not step.permit_solution:
        lines.append("- Der Schueler BETTELT um die Loesung. Freundlich ablehnen, aktivierende Frage stellen, Stufe NICHT erhoehen.")
    if step.intent == "simpler":
        lines.append("- Der Schueler versteht die aktuelle Erklaerung NICHT oder wuenscht eine ANDERE DARSTELLUNG. Erklaere DENSELBEN Punkt nochmal anders: kleinerer Schritt, Alltagsbeispiel mit konkreten Zahlen, andere Worte. Wuenscht er eine SKIZZE, baue einen passenden [[FIGUR]]-Block ein. Nichts Neues verraten, Stufe nicht erhoehen.")
    if step.intent == "step":
        lines.append("- Der Schueler hat einen EIGENEN Schritt gemacht (siehe Pruefung). Ist er richtig: konkret bestaetigen und zum naechsten Schritt ermutigen – KEINE zusaetzliche Hilfe geben, er schafft es gerade selbst.")
    if step.intent == "correct":
        lines.append("- Die Antwort ist KORREKT. Bestaetige knapp und ermutigend, erklaere kurz warum.")
    if step.intent == "post_solved":
        lines.append("- Die Aufgabe ist BEREITS GELOEST. Keine neue Leiter: beantworte Verstaendnisfragen kurz oder gratuliere; lade zu einer neuen Aufgabe ein.")
    if step.permit_solution and verification.solution:
        lines.append(f"- Stufe 4 freigegeben. Interne Loesung (jetzt zeigbar): {verification.solution}")
    elif verification.solution:
        lines.append("- Interne Loesung ist bekannt, aber NOCH GESPERRT – nicht verraten.")
    return "\n".join(lines)


def _build_system(step, verification, exercise_text, exercise_expr, grade_level=None,
                  language="de"):
    """System als Blockliste – grosser Prompt gecacht, Regie pro Turn frisch."""
    regie = _regie(step, verification, exercise_text, exercise_expr, grade_level)
    if (language or "de").startswith("en"):
        regie += ("\n- WICHTIG: Der Schueler nutzt die App auf ENGLISCH. "
                  "Antworte IMMER auf Englisch (alle Erklaerungen, Fragen und Hinweise).")
    return [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": regie},
    ]


# Kontext-/Kostendeckel: nur die juengsten Nachrichten gehen an die API.
HISTORY_LIMIT = 12


def _image_block(image: tuple[bytes, str]) -> dict:
    import base64

    data, media_type = image
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode(),
        },
    }


def _history_to_messages(history: list[dict], image: tuple[bytes, str] | None = None,
                         last_image: tuple[bytes, str] | None = None) -> list[dict]:
    if len(history) > HISTORY_LIMIT:
        # Eroeffnungsnachricht (Aufgabenstellung) behalten + juengster Verlauf
        history = [history[0]] + history[-(HISTORY_LIMIT - 1):]
    msgs = []
    for m in history:
        role = "assistant" if m["role"] == "tutor" else "user"
        msgs.append({"role": role, "content": m["text"]})
    if not msgs or msgs[0]["role"] != "user":
        msgs.insert(0, {"role": "user", "content": "(Aufgabe gestartet)"})
    if image is not None:
        # Aufgaben-Figur (Foto) in die erste User-Nachricht einbetten – das
        # Modell sieht sie damit in jedem Turn (wichtig fuer Geometrie).
        first_text = msgs[0]["content"] if isinstance(msgs[0]["content"], str) else "(Aufgabe gestartet)"
        msgs[0]["content"] = [_image_block(image), {"type": "text", "text": first_text}]
    if last_image is not None:
        # Zeichnung/Foto der AKTUELLEN Schueler-Nachricht in die letzte
        # User-Nachricht einbetten. Nur das juengste Bild geht mit – aeltere
        # Nachrichten-Bilder stehen als erkannter Text im Verlauf (Kostendeckel).
        for m in reversed(msgs):
            if m["role"] == "user":
                if isinstance(m["content"], str):
                    m["content"] = [_image_block(last_image), {"type": "text", "text": m["content"]}]
                else:
                    m["content"] = [_image_block(last_image)] + list(m["content"])
                break
    return msgs


def stream_reply(history, step: LadderStep, verification: Verification,
                 exercise_text: str, exercise_expr: str | None,
                 grade_level: str | None = None,
                 image: tuple[bytes, str] | None = None,
                 usage_out: dict | None = None,
                 last_image: tuple[bytes, str] | None = None,
                 language: str = "de"):
    """Generator, der Text-Chunks der Tutor-Antwort liefert (Streaming).

    ``usage_out``: optionales dict, das nach Stream-Ende mit ``model`` und
    ``usage`` (Token-Verbrauch der API-Antwort) gefuellt wird – Grundlage
    der Admin-Kostenauswertung. Im Mock-/Fehlerfall bleibt es leer.
    ``language``: App-Sprache des Schuelers – der Tutor antwortet darin.
    """
    if not (settings.anthropic_api_key and anthropic):
        yield from _mock_reply(step, verification, exercise_text, language)
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # Aufgaben mit Figur brauchen das starke Modell (Bild lesen = Kernaufgabe)
    model = (settings.anthropic_model_smart if (image or last_image)
             else pick_model(exercise_text, exercise_expr))
    system = _build_system(step, verification, exercise_text, exercise_expr, grade_level,
                           language)
    messages = _history_to_messages(history, image, last_image)
    produced = False
    try:
        with client.messages.stream(model=model, max_tokens=550, system=system, messages=messages) as stream:
            for text in stream.text_stream:
                produced = True
                yield text
            if usage_out is not None:
                usage_out["model"] = model
                usage_out["usage"] = stream.get_final_message().usage
    except Exception as exc:
        # KEIN stiller Mock mehr: der passte nicht zur Aufgabe und der Betreiber
        # erfuhr nie, dass die KI down ist. Ehrlich melden + Fehler ins Log.
        log.exception("Anthropic-Stream fehlgeschlagen (Antwort begonnen: %s)", produced)
        from . import alert

        alert.notify("ki", f"{type(exc).__name__}: {exc}")
        if produced:
            yield t(language,
                    "\n\n⚠️ (Die Verbindung ist mittendrin abgebrochen – frag einfach nochmal, dann mache ich fertig.)",
                    "\n\n⚠️ (The connection dropped mid-answer – just ask again and I'll finish.)")
        else:
            yield t(language,
                    "⚠️ Ich habe gerade technische Probleme und kann dir nicht richtig antworten. "
                    "Schick deine Nachricht in einem Moment einfach nochmal – dein Fortschritt bleibt erhalten.",
                    "⚠️ I'm having technical trouble right now and can't answer properly. "
                    "Please send your message again in a moment – your progress is saved.")


def _mock_reply(step: LadderStep, verification: Verification, exercise_text: str,
                language: str = "de"):
    """Deterministische Antworten ohne API-Key – haelt die Leiter trotzdem ein."""
    if step.intent == "post_solved":
        text = t(language,
                 "Die hast du schon gelöst 🙂 Wenn du magst, erklär ich dir einen Schritt genauer – oder du startest eine neue Aufgabe.",
                 "You already solved this one 🙂 If you like, I can explain a step in more detail – or start a new task.")
    elif step.intent == "correct":
        text = t(language,
                 "Stark, das stimmt! 🎉 Du hast sauber nach der Variablen aufgelöst. Mag noch eine Aufgabe?",
                 "Great, that's correct! 🎉 You solved for the variable cleanly. Want another task?")
    elif step.intent == "plea":
        text = t(language,
                 "Mach ich extra nicht 🙂 – aber ich bring dich hin. Was fällt dir als Erstes auf, das du wegbekommen willst?",
                 "I won't do that on purpose 🙂 – but I'll get you there. What do you notice first that you'd want to get rid of?")
    elif step.intent == "simpler":
        text = t(language,
                 "Okay, ganz langsam nochmal. Schau nur auf die linke Seite der Gleichung: Was steht dort? Sag es mir in deinen eigenen Worten.",
                 "Okay, let's slow down. Look only at the left side of the equation: what's there? Tell me in your own words.")
    elif step.allowed_stage == 1:
        text = t(language,
                 "Kein Stress. Schau die Gleichung an: Was müsstest du zuerst tun, damit die Zahl auf derselben Seite wie das $x$ verschwindet?",
                 "No stress. Look at the equation: what would you do first so the number on the same side as $x$ disappears?")
    elif step.allowed_stage == 2:
        text = t(language,
                 "Kleiner Tipp: Was auf der einen Seite passiert, machst du auch auf der anderen. Überleg, welche Gegen-Rechnung den Störer auffliegen lässt.",
                 "Small hint: whatever you do on one side, do on the other too. Think about which inverse operation removes the extra term.")
    elif step.allowed_stage == 3:
        text = t(language,
                 "Ich mach den ersten Schritt vor: Wir rechnen auf beiden Seiten $-5$. Was steht dann links, und was rechts? Rechne den nächsten Schritt selber.",
                 "I'll show the first step: we subtract $5$ on both sides. What's on the left then, and on the right? Do the next step yourself.")
    else:
        sol = verification.solution or t(language, "die Loesung", "the solution")
        text = t(language,
                 f"Okay, jetzt gemeinsam bis zum Schluss: erst auf beiden Seiten $-5$, dann durch den Koeffizienten teilen. Damit kommst du auf {sol}. Probier den letzten Schritt nochmal selbst nach.",
                 f"Okay, let's finish together: first subtract $5$ on both sides, then divide by the coefficient. That gives you {sol}. Try the last step yourself once more.")
    # in kleinen Haeppchen ausgeben, damit sich Streaming echt anfuehlt
    for chunk in re.findall(r"\S+\s*", text):
        yield chunk
