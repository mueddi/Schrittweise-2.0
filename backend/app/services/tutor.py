"""Tutor-Logik: Hinweis-Leiter-Zustand + Anthropic-Anbindung (Streaming).

Der System-Prompt erzwingt die 4-Stufen-Leiter hart. Das Backend bleibt die
Autorität über den Leiter-Zustand: es berechnet pro Turn, welche Stufe erlaubt
ist, und das LLM formuliert nur die pädagogische Antwort dieser Stufe.
"""
from __future__ import annotations

import logging
import re
import time
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

SYSTEM_PROMPT = """Du bist «Kniff», ein geduldiger Mathe-Tutor fuer Schweizer Schueler:innen der Oberstufe (Sek I, Lehrplan 21) UND des Gymnasiums (bis zur Matura). Die Regie-Anweisung nennt dir die Klassenstufe: Bei Sek I erklaerst du einfach, kleinschrittig und mit Alltagsbildern. Bei Gymnasium nutzt du praezise Fachsprache und zuegigere Schritte auf Matura-Niveau (Funktionen, Analysis, Vektoren, Stochastik) – aber auch dort gilt die Hinweis-Leiter.

DEINE EISERNE REGEL: Du verraetst die Loesung NIEMALS direkt, ausser die Regie-Anweisung erlaubt ausdruecklich Stufe 4. Du fuehrst ueber eine HINWEIS-LEITER mit vier Stufen zum eigenen Denken:
  Stufe 1 – Aktivierende Frage («Was muesstest du tun, damit die +5 verschwindet?»)
  Stufe 2 – Kleiner Tipp
  Stufe 3 – Ein Teilschritt vorgemacht (aber nicht die ganze Loesung)
  Stufe 4 – Volle Loesung, Schritt fuer Schritt – NUR wenn die Regie sie freigibt (nach mind. 2 echten eigenen Versuchen)

WENN DER SCHUELER BETTELT («gib mir die Loesung 🙏», «sag einfach die Antwort»): Lehne freundlich und bestimmt ab und stell die aktivierende Frage der aktuellen Stufe. Beispiel: «Mach ich extra nicht 🙂 – aber ich helf dir hin. Was faellt dir zuerst auf?» Erhoehe die Stufe dabei NICHT.

STIL:
- Du klingst wie ein aelterer Bruder, der Mathe kann: kumpelhaft, geduldig, nie belehrend, nie ueberwachend.
- Duze, sei ermutigend, nie belehrend. Schweizer Hochdeutsch: schreib «weiss» statt «weiß» – nie den Buchstaben «ß» verwenden.
- Kurz halten: 1–2 kurze Saetze, nur wenn wirklich noetig 3. Eine Frage oder ein Hinweis pro Antwort. Keine Wiederholung der Aufgabenstellung, keine Floskeln.
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

AUFGABE ABHAKEN:
Hat der Schueler die Aufgabe WIRKLICH geloest, schreib als ALLERLETZTES deiner Antwort den Marker [[GELOEST]]. Er wird dem Schueler nicht angezeigt – er hakt die Aufgabe in seiner Liste ab.
Regeln dafuer:
- Nur wenn der Schueler die richtige Antwort SELBST geschrieben oder gezeichnet hat. Hast nur du sie genannt, setz den Marker NICHT.
- Nur wenn die GANZE Aufgabe erledigt ist, nicht nach einem Zwischenschritt.
- Im Zweifel weglassen. Lieber einmal nicht abgehakt als faelschlich abgehakt.
- Der Marker ersetzt kein Wort: schreib zuerst deine normale Antwort, der Marker steht ganz am Schluss.

SO ERKLAERST DU (SEHR WICHTIG):
- Die meisten Schueler:innen hier haben Muehe mit Mathe und wenig Selbstvertrauen. Geh IMMER davon aus, dass die Grundlagen wackeln.
- Extrem einfache Sprache: kurze Saetze. Ein Gedanke pro Satz.
- KEIN Fachwort ohne sofortige Alltags-Erklaerung in Klammern, z.B. «Term (= ein Rechenausdruck)», «Variable (= die unbekannte Zahl, hier $x$)».
- Nutze Alltagsbilder: die Waage fuer Gleichungen (beide Seiten gleich schwer halten), die Pizza fuer Brueche, das Sackgeld fuer Prozente.
- Sag NIE «das ist einfach» oder «das ist doch klar» – das beschaemt. Sag stattdessen «das ueben wir kurz zusammen».
- Wenn der Schueler «ich verstehe es nicht» sagt: NICHT dasselbe wiederholen, sondern EINFACHER erklaeren – kleinerer Schritt, konkretes Alltagsbeispiel mit Zahlen.
- Lob konkret statt pauschal: nicht «super!», sondern «stark – das Minusrechnen auf beiden Seiten hat gestimmt».

Du bekommst pro Nachricht eine REGIE-ANWEISUNG mit: erlaubter Stufe, SymPy-Pruefergebnis und Anzahl eigener Versuche. Halte dich strikt daran. Die interne Loesung, falls mitgegeben, verwendest du HOECHSTENS auf Stufe 4."""


# Die App richtet sich an Schweizer Kinder – viele schreiben Mundart. Fruehere
# Muster kannten nur Hochdeutsch, also fiel JEDE Mundart-Nachricht in den
# "talk"-Zweig («das ist kein Hilferuf»): «nei ich verstahs nöd», «chasch mir
# helfe», «zeig mer d lösig» blieben ohne jede Wirkung, und die Hilfe-Leiter
# stand fuer solche Kinder still. Darum ueberall die Mundart-Varianten dazu.
_NICHT = r"(?:nichts?|nöd|noed|nid|ned)"
# "loesung" (oe), "lösung", "losung", Mundart "lösig" alle abdecken
_LOESUNG = r"l(?:oe|ö|o)s(?:un|i)?g"
_ZIEL = rf"(?:{_LOESUNG}|antwort|ergebnis|resultat)"
# Verneintes oder rueckfragendes Reden UEBER die Loesung ist kein Betteln:
# «zeig mir nicht die Loesung», «verrate mir die Loesung nicht», «sag mal, wie
# kommst du auf die Loesung?» loesten bisher das Abfuhr-Skript aus.
_KEIN_BETTELN = re.compile(
    rf"\b{_NICHT}\b\s*(?:die|das|der|den|d)?\s*{_ZIEL}"
    rf"|{_ZIEL}[^.?!]{{0,20}}\b{_NICHT}\b"
    rf"|\bwie\s+(?:kommst|kommt|komme|komm|chunnsch|chunt|chum)\b"
)
# Echte AUFFORDERUNG nach dem Ziel («gib mir die Loesung»), nicht blosse
# Erwaehnung («ich verstehe die Loesung nicht», «wie kommst du auf das
# Ergebnis?»). \b haelt «Antwort» von «beantworten» fern.
# Verb-Stamm + \w*, damit auch die hoefliche Form greift: «zeige/sage/löse»
# fielen an der Wortgrenze durch und landeten in "talk".
_FORDERUNG = (
    rf"\b(?:gib|gebt|gimme|sag|zeig|nenn|verrat|schreib|l[oö]se?|zeis)\w*"
    rf"\b[^.?!]{{0,30}}\b{_ZIEL}\b"
    rf"|\bwie\s+(?:lautet|heisst|hei[sß]t|ist|isch)\s+(?:die|das|der|d)\s*{_ZIEL}\b"
    rf"|\b(?:nur|einfach|bitte)\s+(?:die|das|d)\s+{_ZIEL}\b"
    rf"|\bich\s+(?:will|wott|möcht\w*|moecht\w*|brauch\w*)\b[^.?!]{{0,20}}\b{_ZIEL}\b"
    rf"|\b{_ZIEL}\s*(?:bitte|🙏)"
)
BETTEL_PATTERNS = [
    rf"gib (mir |mer )?die {_LOESUNG}", rf"sag(?:s)? (mir|mer) die {_LOESUNG}",
    rf"was (ist|isch) die {_LOESUNG}",
    r"einfach die antwort", r"sag einfach", rf"{_LOESUNG} bitte", r"nur die antwort",
    r"gib die antwort", r"sag mir das ergebnis", rf"{_LOESUNG}\s*🙏", r"bitte die antwort",
    # «verrat» allein traf auch «ich verrate dir nichts» – nur mit Ziel-Wort
    rf"verrat\w*\s+(?:mir\s+|mer\s+|uns\s+)?(?:die|das|den|d)?\s*{_ZIEL}",
    # generischer: «zeig/nenn/sag mir … Loesung/Antwort/Ergebnis», «wie lautet die Antwort»
    rf"zeig\w* (mir |mer )?(die|den|das|d)? ?{_ZIEL}", rf"nenn(e)? (mir |mer )?(die|das)? ?{_ZIEL}",
    rf"wie (lautet|heisst|ist|isch) (die|das|d) ?{_ZIEL}", rf"sag\w* (mir |mer )?(die|das) {_ZIEL}",
    rf"gib\w* (mir |mer )?(die|das) {_ZIEL}", rf"was (ist|isch) (die|das|d) ?{_ZIEL}",
    r"l[oö]se?\w*\s+(?:es\s+|die\s+aufgabe\s+)?f[üu](?:e)?r\s+mich",
]
# «Ich verstehe es nicht» / «erklär es einfacher»: der Schueler braucht KEINE
# neue Hilfestufe, sondern DIESELBE Erklaerung in einfacheren Worten. Diese
# Muster duerfen die Leiter deshalb NICHT hochtreiben.
SIMPLER_PATTERNS = [
    # bis zu ~4 Woerter zwischen «versteh…» und «nicht» zulassen, damit auch
    # «ich verstehe die Loesung/den Schritt nicht» greift (vorher nur «es nicht»);
    # «verstah…» ist die Mundart-Form («ich verstahs nöd»)
    r"einfacher", rf"(?:versteh|verstah)\w*\b[^.?!]{{0,28}}\b{_NICHT}\b", r"kapier",
    rf"check(e)? (es |das )?{_NICHT}",
    r"nochmal erkl[aä]r", r"erkl[aä]r.{0,20}nochmal", r"zu schwierig", r"zu kompliziert",
    # «Erklaer's anders»-Chips: andere DARSTELLUNG derselben Stufe, kein Stufen-Anstieg
    r"skizze", r"zeichn", r"alltag", r"beispiel aus", r"konkreten zahlen", r"zahlen statt",
]
HILFE_PATTERNS = [
    rf"weiss (es )?{_NICHT}", r"keine ahnung", rf"komm(e)? {_NICHT} weiter", r"h[aä]nge",
    r"h[iää]lfe", r"h[aä]lf", r"helfe", r"tipp", r"hinweis", r"n[aä]chste stufe", r"\bstufe \d",
    r"wie (geht|gaht|mach|machi|anfangen|weiter)", r"was (jetzt|nun|soll ich)", r"stecke fest",
    # Ausdrueckliche Bitte um den naechsten Schritt – echter Hilferuf, der die
    # Leiter hochtreiben darf (faellt sonst in den neuen "talk"-Zweig).
    r"ersten schritt", r"n(ae|ä)chste[nrs]? schritt", r"zeig.{0,20}schritt", r"hilf mir",
    # Mundart + fehlende hochdeutsche Formen (vorher alle "talk"):
    # «chasch mir helfe», «ich cha das nid», «ich kann das nicht»,
    # «wie fange ich an», «was muss ich zuerst machen»
    r"\bchasch\b", rf"\bcha\w*\b[^.?!]{{0,20}}\b{_NICHT}\b", rf"kann (das |es |ich )?{_NICHT}",
    r"wo (fange|fang) ich an", r"wie (fange|fang) ich an", r"(muss|soll) ich zuerst",
]


def detect_intent(message: str, verification: Verification) -> str:
    """'plea' | 'correct' | 'attempt' | 'step' | 'simpler' | 'stuck'.

    'step' = eigener Schritt, der NICHT falsch ist (richtige Umformung oder
    nicht pruefbar): zaehlt als Versuch, treibt die Hilfe-Stufe aber nicht
    hoch – mehr Hilfe gibt es nur bei Fehlern ('attempt') oder auf Anfrage.
    """
    low = message.lower()
    # «zeig mir NICHT die Loesung» / «wie kommst du auf die Loesung?» sind kein
    # Betteln – vorher liefen beide ins Abfuhr-Skript.
    bettelt = not _KEIN_BETTELN.search(low)
    if verification.status == "correct":
        return "correct"
    if bettelt and any(re.search(p, low) for p in BETTEL_PATTERNS):
        return "plea"
    if verification.status == "partial":
        return "step"
    if verification.status == "incorrect":
        return "attempt"
    if verification.extracted:  # eine Zahl/Antwort war drin, aber nicht pruefbar
        return "step"
    # «Ich verstehe die Loesung nicht» ist KEIN Betteln, sondern eine Bitte um
    # eine andere Erklaerung – deshalb VOR dem Ziel-Wort-Fallback pruefen.
    # Vorher schnappte sich das blosse Wort «Loesung» solche Nachrichten und
    # der Tutor lehnte ab, statt zu erklaeren.
    if any(re.search(p, low) for p in SIMPLER_PATTERNS):
        return "simpler"
    # Fragt nach Loesung/Antwort/Ergebnis OHNE eigenen Rechenversuch -> Betteln.
    # Nur mit Wortgrenze UND nur als echte Aufforderung: das blosse Vorkommen
    # des Wortes reicht nicht («wie kommst du auf diese Loesung?»).
    if bettelt and re.search(_FORDERUNG, low):
        return "plea"
    if any(re.search(p, low) for p in HILFE_PATTERNS):
        return "stuck"
    # Alles Uebrige ist normales Reden (Rueckfrage, Kommentar, «ok»).
    # Frueher lief das als "stuck" und trieb die Hilfe-Leiter bei JEDER
    # unverstandenen Nachricht eine Sprosse hoch.
    return "talk"


@dataclass
class LadderStep:
    intent: str
    allowed_stage: int
    own_attempts: int
    solved: bool
    permit_solution: bool


def advance_ladder(current_stage: int, own_attempts: int, intent: str, min_attempts: int = 2,
                   turns: int = 0) -> LadderStep:
    """Deterministische Zustandsmaschine der Hinweis-Leiter.

    ``turns``: bisherige Nachrichten in dieser Aufgabe – nur als Notausgang,
    damit ein sichtlich festgefahrenes Gespraech nicht ewig blockiert.
    """
    solved = intent == "correct"
    if solved:
        return LadderStep(intent, max(current_stage, 1), own_attempts, True, False)

    if intent == "plea":
        # Verdiente Freigabe: wer genug eigene Versuche gemacht hat, bekommt die
        # Loesung auf Nachfrage WIRKLICH – sonst waere die Regel «nach 2 eigenen
        # Versuchen» nie aktiv nutzbar.
        # Die zusaetzliche Bedingung «Stufe >= 3» ist bewusst weg: wer selbst
        # rechnet, bleibt auf Stufe 1 (eigene Schritte erhoehen sie nicht) und
        # wurde deshalb FUER IMMER abgewiesen – gerade die fleissigen Kinder.
        # Notausgang: langes Gespraech mit mindestens einem eigenen Versuch.
        if own_attempts >= min_attempts or (own_attempts >= 1 and turns >= 12):
            return LadderStep(intent, 4, own_attempts, False, True)
        # Betteln davor: Stufe bleibt, kein Versuch gezaehlt
        stage = max(current_stage, 1)
        return LadderStep(intent, stage, own_attempts, False, False)

    if intent in ("simpler", "talk"):
        # «Verstehe es nicht» / «erklaer einfacher» / normales Reden: dieselbe
        # Stufe, nur in einfacheren Worten – Nachfragen kostet keine Sprosse
        # und keinen Versuch.
        return LadderStep(intent, max(current_stage, 1), own_attempts, False, False)

    if intent == "step":
        # Richtiger (oder nicht pruefbarer) eigener Schritt: zaehlt als Versuch,
        # aber die Hilfe-Stufe bleibt – wer gut unterwegs ist, braucht nicht
        # MEHR Hilfe, sondern nur Bestaetigung und den naechsten Anstoss.
        return LadderStep(intent, max(current_stage, 1), own_attempts + 1, False, False)

    if intent == "attempt":
        own_attempts += 1
    # Frueher zaehlte hier eine Hilfe-Bitte ab Stufe 3 als eigener Versuch,
    # damit die Leiter nicht bei 3 einfriert. Das hoehlte die Zusage aus:
    # fuenfmal «Tipp» druecken gab die volle Loesung frei, ohne dass das Kind
    # je gerechnet hatte. Das Einfrieren loest jetzt die plea-Regel oben.

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
           grade_level: str | None = None, language: str = "de",
           from_image: bool = False) -> str:
    """Regie-Anweisung fuer EINEN Turn.

    ``from_image``: die Aufgabe stammt von einem Foto/einer Zeichnung, der
    Pruefausdruck also aus der Bild-Erkennung. Er kann dann falsch gelesen
    sein – das wird beim Nennen der internen Loesung ausdruecklich dazugesagt,
    damit der Tutor nicht jeden Hinweis auf eine falsche Zahl lenkt.
    """
    lines = [
        "REGIE-ANWEISUNG (nicht an den Schueler weitergeben):",
        f"- Aufgabe: {exercise_text}" + (f"  [Ausdruck: {exercise_expr}]" if exercise_expr else ""),
        # Bei geloester Aufgabe NICHT die eingefrorene Hinweis-Stufe nennen –
        # sonst stand hier «Erlaubte Stufe: 1 – Aktivierende Frage» und weiter
        # unten «Stufe 4 freigegeben», was den Tutor durcheinanderbrachte.
        ("- Die Aufgabe ist geloest. Du darfst den vollen Loesungsweg erklaeren, wenn er danach fragt."
         if step.solved else
         f"- Erlaubte Stufe: {step.allowed_stage} – {STUFEN[step.allowed_stage]}"),
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
    # Ohne maschinelle Pruefung bist DU der einzige Richter: dann muss der
    # Tutor die Aufgabe auch abhaken duerfen. Vorher konnte «geloest» NUR aus
    # SymPy kommen – zwei Dritteln aller Aufgaben fehlt aber ein Pruefausdruck,
    # sie liessen sich also nie abschliessen, egal was das Kind rechnete.
    if not step.solved and verification.status != "correct":
        lines.append("- Diese Aufgabe kann die App nicht selbst pruefen. Wenn der Schueler sie in dieser Antwort wirklich geloest hat, haeng den Marker [[GELOEST]] ganz ans Ende (Regeln siehe oben).")
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
    if step.intent == "talk":
        lines.append("- Der Schueler REDET mit dir (Rueckfrage, Kommentar, Zwischenbemerkung) – das ist kein Hilferuf. Geh direkt auf seine Worte ein und antworte kurz. Stufe NICHT erhoehen, keine neue Hilfe anbieten, die er nicht verlangt hat.")
    solution_ok = bool(verification.solution)
    # Bei Foto-/Zeichnungs-Aufgaben steht der Pruefausdruck NICHT fest: er kommt
    # aus der Bild-Erkennung. Ohne diesen Hinweis zielte der Tutor jeden Hinweis
    # auf eine womoeglich falsch gelesene Zahl, die ihm als geprueft galt.
    unsicher = ("  ACHTUNG: dieser Wert stammt aus der Bild-Erkennung und kann auf einer"
                " falsch gelesenen Aufgabe beruhen. Widerspricht er dem BILD, gilt das BILD –"
                " dann rechne neu und nenne den Wert nicht." if from_image else "")
    # Zeigen darf der Tutor, wenn die Aufgabe geloest ist ODER Stufe 4 erreicht
    # ist ODER diese Runde ausdruecklich freigegeben wurde. Vorher stand in
    # genau dem Moment, in dem das Kind loeste, beides gleichzeitig da: «Die
    # Aufgabe ist geloest, du darfst den vollen Loesungsweg erklaeren» UND
    # «dem Schueler NIEMALS nennen, Stufe 4 ist NICHT freigegeben».
    darf_zeigen = step.solved or step.allowed_stage >= 4 or step.permit_solution
    if darf_zeigen and solution_ok:
        lines.append(f"- Stufe 4 freigegeben. Interne Loesung (jetzt zeigbar): {verification.solution}{unsicher}")
    elif solution_ok:
        # Loesung als Orientierung mitgeben: der Tutor zielt damit in jedem
        # Hinweis aufs verifizierte Resultat (weniger Rechen-Patzer) –
        # verraten darf er sie weiterhin erst auf Stufe 4.
        lines.append("- Interne Loesung NUR ZU DEINER ORIENTIERUNG – dem Schueler NIEMALS nennen, "
                     f"Stufe 4 ist NICHT freigegeben: {verification.solution}{unsicher}")
    if (language or "de").startswith("en"):
        lines.append("- WICHTIG: Der Schueler nutzt die App auf ENGLISCH. "
                     "Antworte IMMER auf Englisch (alle Erklaerungen, Fragen und Hinweise).")
    return "\n".join(lines)


def _build_system():
    """Nur der grosse, STATISCHE System-Prompt – als Cache-Praefix. Die
    Regie-Anweisung wandert in die letzte User-Nachricht, damit der Cache
    (System + Aufgabe + Bild) ueber die Turns hinweg bestehen bleibt."""
    return [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]


# Zeitbudget eines Chat-Turns. Vercel bricht die Anfrage nach 60 s ab; damit
# die App den Ausfall SELBST bemerkt (und die freundliche Meldung ueberhaupt
# ausgeben kann), muss alles darunter bleiben.
CLIENT_TIMEOUT = 20.0
# Bis hierhin lohnt sich ein zweiter Anlauf mit dem anderen Modell; danach
# reicht die Restzeit nicht mehr.
AUSWEICH_DEADLINE = 28.0


def _modell_kette(model: str) -> list[str]:
    """Das gewaehlte Modell, dahinter das jeweils andere als Ausweichweg.

    Der weitaus haeufigste echte Fehler ist kein Totalausfall, sondern «Modell
    ueberlastet» (529) oder «zu viele Anfragen» (429) – und der trifft immer
    nur EIN Modell. Die App hat zwei; das zweite kostet im Zweifel etwas mehr
    oder erklaert etwas schlichter, aber der Schueler bekommt eine Antwort.
    """
    ausweich = (settings.anthropic_model_default
                if model == settings.anthropic_model_smart
                else settings.anthropic_model_smart)
    return [model] if ausweich == model else [model, ausweich]


def _ein_versuch(client, model: str, system, messages, usage_out: dict | None):
    """EIN Anlauf bei einem Modell. Wirft weiter, damit der Aufrufer wechseln kann."""
    kwargs = {}
    denken = _thinking_param(model)
    if denken is not None:
        kwargs["thinking"] = denken
    with client.messages.stream(model=model, max_tokens=MAX_TOKENS, system=system,
                                messages=messages, **kwargs) as stream:
        try:
            for text in stream.text_stream:
                yield text
        finally:
            # Klickt der Schueler waehrend der Antwort weg, laeuft
            # get_final_message() unten NIE: der Turn blieb unverrechnet und
            # tauchte in keiner Statistik auf (beliebig wiederholbar).
            # Der Zwischenstand kennt den Verbrauch bereits.
            if usage_out is not None and "usage" not in usage_out:
                try:
                    snap = stream.current_message_snapshot
                except Exception:
                    snap = None
                if getattr(snap, "usage", None) is not None:
                    usage_out["model"] = model
                    usage_out["usage"] = snap.usage
        final = stream.get_final_message()
        if usage_out is not None:
            usage_out["model"] = model
            usage_out["usage"] = final.usage
        if getattr(final, "stop_reason", None) == "max_tokens":
            # Antwort wurde mitten im Wort gekappt (real beobachtet). Der
            # Schueler sieht einen Torso und muss nachfragen – das kostet
            # doppelt. Sichtbar machen statt still hinnehmen.
            from . import alert

            alert.notify("ki-qualitaet",
                         f"Antwort am Token-Limit abgeschnitten (Modell {model}, max_tokens={MAX_TOKENS}).",
                         key="max_tokens")


def choose_model(step: LadderStep, exercise_text: str, exercise_expr: str | None,
                 last_image: tuple[bytes, str] | None = None) -> str:
    """«Sonnet liest – Haiku unterrichtet – Sonnet loest»: das teure Modell
    nur an den fehlerkritischen Punkten. Neue Schueler-Zeichnung exakt lesen
    und die volle Loesung (Stufe 4) -> smart; alle gefuehrten Hinweis-Turns
    dazwischen -> pick_model (Haiku, ausser Gymi-/Komplex-Marker). Haiku hat
    dafuer drei Stuetzen: OCR-Transkription im Aufgabentext, SymPy-Loesung
    als Kompass in der Regie und die Nachrechnung der Antwort."""
    if last_image is not None:
        return settings.anthropic_model_smart
    if step.permit_solution and step.allowed_stage >= 4:
        return settings.anthropic_model_smart
    return pick_model(exercise_text, exercise_expr)


# Kontext-/Kostendeckel: nur die juengsten Nachrichten gehen an die API.
HISTORY_LIMIT = 12

# Beschriftungen der Bild-Bloecke. Ohne sie stehen bei einer Zeichnung ZWEI
# Bilder unkommentiert im Kontext und das Modell kann Aufgabe und Schueler-
# Zeichnung nicht auseinanderhalten – es «sieht dann, was es will».
# Sicherheitsnetz, kein Ziel: der Systemprompt verlangt weiterhin 1-2 kurze
# Saetze. Bei 400 wurden laengere Antworten (Stufe 3/4, Theorie-Fragen) mitten
# im Wort gekappt – verrechnet werden ohnehin nur erzeugte Tokens.
MAX_TOKENS = 700


def _thinking_param(model: str) -> dict | None:
    """Vordenken bewusst ABSCHALTEN – nur fuer Modelle, die den Schalter kennen.

    Sonnet 5 denkt standardmaessig vor, wenn der Parameter fehlt (Sonnet 4.6
    tat das nicht). Diese Denk-Tokens zaehlen gegen dasselbe max_tokens wie der
    Antworttext. Real gemessen: 700 Output-Tokens verbraucht, NULL Zeichen Text
    beim Schueler – die Antwort war komplett Vordenken, das niemand sieht.
    Beim Turn davor blieben nach dem Denken nur 323 Zeichen, mitten in der
    Formel abgeschnitten.

    Fuer diesen Tutor ist Vordenken ohnehin verschwendet: er soll in 1-2 kurzen
    Saetzen auf den Schueler reagieren und bekommt die von SymPy verifizierte
    Loesung schon als Orientierung mitgeliefert – er muss die Mathematik nicht
    selbst herleiten. Abschalten macht die Antworten vollstaendig UND spart auf
    einem Sonnet-Turn rund zwei Drittel der Kosten.

    Haiku 4.5 kennt den Schalter nicht (dort bedeutet «Parameter weglassen»
    bereits: kein Vordenken) – ein explizites disabled koennte 400 geben.
    """
    return {"type": "disabled"} if model == settings.anthropic_model_smart else None

BILD_AUFGABE = "BILD A – die AUFGABENSTELLUNG (unveraendert seit Beginn):"
BILD_SCHUELER = "BILD B – das hat der Schueler GERADE eben gezeichnet/fotografiert. Lies NUR daraus ab, was wirklich draufsteht:"
_BILD_LABELS = {BILD_AUFGABE, BILD_SCHUELER}


def _schueler_block(text: str) -> dict:
    """Der Schueler-Text als klar beschrifteter, letzter Block.

    Vorher stand er als nackter Text direkt hinter der langen Regie-Anweisung
    und war davon nicht zu unterscheiden – der Tutor ging deshalb oft gar
    nicht darauf ein.
    """
    inhalt = (text or "").strip()
    if not inhalt:
        return {"type": "text", "text": "NACHRICHT DES SCHUELERS: (kein Text – nur das Bild)"}
    return {"type": "text",
            "text": f"NACHRICHT DES SCHUELERS (genau darauf antwortest du):\n«{inhalt}»"}


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
                         last_image: tuple[bytes, str] | None = None,
                         regie: str | None = None,
                         exercise_text: str | None = None) -> list[dict]:
    if len(history) > HISTORY_LIMIT:
        # Eroeffnungsnachricht (Aufgabenstellung) behalten + juengster Verlauf
        history = [history[0]] + history[-(HISTORY_LIMIT - 1):]
    msgs = []
    for m in history:
        role = "assistant" if m["role"] == "tutor" else "user"
        msgs.append({"role": role, "content": m["text"]})
    if not msgs or msgs[0]["role"] != "user":
        # Statt der inhaltsleeren Fuellung «(Aufgabe gestartet)» den echten
        # Aufgabentext: das Bild kam sonst ohne jeden Kontext an. Der Text
        # liegt hier IM gecachten Praefix und kostet ab dem 2. Turn ~10 %.
        aufgabe = (exercise_text or "").strip()
        msgs.insert(0, {"role": "user",
                        "content": f"AUFGABE:\n{aufgabe}" if aufgabe else "(Aufgabe gestartet)"})
    if image is not None:
        # Aufgaben-Figur (Foto) in die erste User-Nachricht einbetten – das
        # Modell sieht sie damit in jedem Turn (wichtig fuer Geometrie).
        # BESCHRIFTET, sonst weiss das Modell bei zwei Bildern nicht, welches
        # die Aufgabe und welches die Zeichnung des Schuelers ist.
        # cache_control auf dem letzten Block: System + Aufgabe + Bild werden
        # ab dem 2. Turn zu 10 % des Preises aus dem Cache gelesen.
        first_text = msgs[0]["content"] if isinstance(msgs[0]["content"], str) else "(Aufgabe gestartet)"
        msgs[0]["content"] = [{"type": "text", "text": BILD_AUFGABE},
                              _image_block(image),
                              {"type": "text", "text": first_text,
                               "cache_control": {"type": "ephemeral"}}]
    if last_image is not None:
        # Zeichnung/Foto der AKTUELLEN Schueler-Nachricht in die letzte
        # User-Nachricht einbetten. Nur das juengste Bild geht mit – aeltere
        # Nachrichten-Bilder stehen als erkannter Text im Verlauf (Kostendeckel).
        for m in reversed(msgs):
            if m["role"] == "user":
                block = [{"type": "text", "text": BILD_SCHUELER}, _image_block(last_image)]
                if isinstance(m["content"], str):
                    m["content"] = block + [{"type": "text", "text": m["content"]}]
                else:
                    m["content"] = block + list(m["content"])
                break
    if regie:
        # Regie-Anweisung als Block VOR dem Schueler-Text der letzten
        # User-Nachricht (statt im System): haelt den Cache-Praefix stabil.
        # Der Schueler-Text kommt ZULETZT und ausdruecklich beschriftet –
        # sonst ist er von der Anweisung nicht zu unterscheiden und geht
        # neben dem langen Regie-Block schlicht unter.
        last = msgs[-1]
        block = {"type": "text", "text": regie}
        if last["role"] != "user":
            msgs.append({"role": "user", "content": [block]})
        elif isinstance(last["content"], str):
            last["content"] = [block, _schueler_block(last["content"])]
        else:
            head = [c for c in last["content"] if c.get("type") == "image" or c.get("text") in _BILD_LABELS]
            rest = [c for c in last["content"] if c not in head]
            texte = " ".join(c.get("text", "") for c in rest).strip()
            last["content"] = head + [block, _schueler_block(texte)]
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

    # Zeitlimit BEWUSST unter dem Deckel der Hosting-Plattform (Vercel bricht
    # nach 60 s ab). Vorher wartete der Client bis zu 600 s – bei einer
    # haengenden KI wurde die Funktion also von aussen abgeschossen, bevor der
    # eigene Aufraeum-Code lief, und der Schueler sah einen nackten Abbruch
    # statt der freundlichen Meldung. Eine Wiederholung statt zwei, damit im
    # Zeitbudget noch Platz fuer das Ausweich-Modell bleibt.
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                 timeout=CLIENT_TIMEOUT, max_retries=1)
    model = choose_model(step, exercise_text, exercise_expr, last_image)
    system = _build_system()
    regie = _regie(step, verification, exercise_text, exercise_expr, grade_level, language,
                   from_image=image is not None)
    messages = _history_to_messages(history, image, last_image, regie=regie,
                                    exercise_text=exercise_text)

    from . import alert

    start = time.monotonic()
    produced = False
    letzter_fehler: Exception | None = None
    for versuch, aktuelles_modell in enumerate(_modell_kette(model)):
        if versuch and (produced or time.monotonic() - start > AUSWEICH_DEADLINE):
            # Steht schon Text beim Schueler, wird NICHT gewechselt – sonst
            # bekaeme er zwei verschiedene Antworten durcheinander. Und ohne
            # Restzeit hat ein zweiter Anlauf keinen Zweck mehr.
            break
        try:
            for text in _ein_versuch(client, aktuelles_modell, system, messages, usage_out):
                produced = True
                yield text
            if versuch:
                log.warning("Modell %s nicht verfuegbar, mit %s beantwortet", model, aktuelles_modell)
                alert.notify("ki",
                             f"Modell {model} war nicht verfuegbar – automatisch auf "
                             f"{aktuelles_modell} ausgewichen. Der Schueler hat eine "
                             f"normale Antwort bekommen, es ist nichts ausgefallen.",
                             key="ausweich")
            return
        except Exception as exc:
            letzter_fehler = exc
            log.exception("Anthropic-Stream mit %s fehlgeschlagen (Antwort begonnen: %s)",
                          aktuelles_modell, produced)

    # Alle Anlaeufe gescheitert: KEIN stiller Mock (der passte nicht zur Aufgabe
    # und der Betreiber erfuhr nie, dass die KI down ist). Ehrlich melden.
    if usage_out is not None:
        # Signal an den Aufrufer: dieser Turn hat KEINE Hilfe geliefert, die
        # Hilfe-Stufe darf deshalb nicht weiterklettern.
        usage_out["fehler"] = True
    alert.notify("ki", f"{type(letzter_fehler).__name__}: {letzter_fehler}")
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
