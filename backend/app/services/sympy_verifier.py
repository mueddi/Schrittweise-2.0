"""Deterministische Mathe-Verifikation mit SymPy.

Die Pädagogik macht das LLM. Diese Funktion sagt nur: ist die Schülerantwort
korrekt / teilweise (gültiger Umformungsschritt) / falsch / nicht prüfbar –
und liefert (intern!) die Lösung, die erst auf Stufe 4 verraten werden darf.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


@dataclass
class Verification:
    status: str  # "correct" | "partial" | "incorrect" | "unknown"
    detail: str  # kurze technische Notiz (nur intern)
    solution: str | None = None  # interne Lösung, NIE ungefiltert an Schüler
    extracted: str | None = None  # was aus der Antwort erkannt wurde
    score: float = 0.0  # feinkörnig intern

    def to_context(self) -> dict:
        """Kompakter Kontext fürs LLM (ohne die Lösung, ausser Stufe 4 erlaubt)."""
        return {"status": self.status, "detail": self.detail, "extracted": self.extracted}


def _normalize(s: str) -> str:
    s = s.strip()
    s = s.replace("−", "-").replace("·", "*").replace("×", "*").replace(":", "/")
    s = s.replace(",", ".")  # Dezimalkomma -> Punkt (Schweiz)
    return s


def _insert_explicit_mult(s: str) -> str:
    """Schul-Lesart erzwingen: implizites Mal EXPLIZIT machen, BEVOR SymPy parst.

    SymPy's implicit multiplication bindet staerker als die Division –
    «3/2y» wuerde zu 3/(2·y). Schueler:innen lesen linear von links nach
    rechts: «3/2y» = (3/2)·y. Darum «2y»→«2*y», «)x»→«)*x», «y(»→«y*(»
    (einzelne Variable, Funktionsnamen wie sqrt( bleiben unberuehrt).
    """
    s = re.sub(r"(\d)\s*(?=[A-Za-z(])", r"\1*", s)
    s = re.sub(r"(\))\s*(?=[A-Za-z0-9(])", r"\1*", s)
    s = re.sub(r"(?<![A-Za-z])([A-Za-z])\s*(?=\()", r"\1*", s)
    return s


def _parse(expr: str):
    return parse_expr(_insert_explicit_mult(_normalize(expr)),
                      transformations=_TRANSFORMS, evaluate=True)


def _split_equation(text: str):
    """'3x+5=20' -> (lhs, rhs) als SymPy-Ausdrücke, sonst None."""
    if "=" not in text:
        return None
    left, _, right = text.partition("=")
    try:
        return _parse(left), _parse(right)
    except Exception:
        return None


def _free_symbol(*exprs):
    syms: set = set()
    for e in exprs:
        syms |= e.free_symbols
    return next(iter(syms)) if len(syms) == 1 else (sorted(syms, key=str)[0] if syms else None)


def _solutions(lhs, rhs, sym):
    try:
        sols = sp.solve(sp.Eq(lhs, rhs), sym, dict=False)
        return [sp.nsimplify(s) if s.is_number else s for s in sols]
    except Exception:
        return []


def _extract_candidates(message: str) -> list[str]:
    """Zieht mögliche Antwort-Fragmente aus dem Schülertext.

    Erkennt 'x = 5', '= 5', ganze Gleichungen, oder eine allein stehende Zahl.
    """
    msg = _normalize(message)
    cands: list[str] = []
    # eigenständige Gleichung im Text zuerst (damit '3x = 15' als Umformung zaehlt)
    if "=" in msg:
        cands.append(msg)
        # Mathe-Fragment um das '=' aus Prosa ziehen ("ich denke 3x = 15" -> "3x = 15"):
        # zusammenhaengende Mathe-Zeichen links/rechts, Prosa-Woerter (>1 Buchstabe) verwerfen
        m = re.search(r"([0-9a-zA-Z+\-*/^().\s]+?)=\s*([0-9a-zA-Z+\-*/^().\s]+)", msg)
        if m:
            lhs_tokens = m.group(1).split()
            # fuehrende Prosa-Woerter (mehrbuchstabig, ohne Ziffern/Operatoren) abwerfen
            while lhs_tokens and re.fullmatch(r"[a-zA-Z]{2,}", lhs_tokens[0]):
                lhs_tokens.pop(0)
            rhs = m.group(2).split()
            rhs_tokens = []
            for t in rhs:
                if re.fullmatch(r"[a-zA-Z]{2,}", t):
                    break  # Prosa nach der Zahl ("15 oder?") kappen
                rhs_tokens.append(t)
            if lhs_tokens and rhs_tokens:
                frag = f"{' '.join(lhs_tokens)} = {' '.join(rhs_tokens)}"
                if frag != msg:
                    cands.append(frag)
    # 'x = ...' (Variable NICHT von Ziffer/Buchstabe direkt gefolgt, sonst ist es ein Koeffizient)
    for m in re.finditer(r"(?<![0-9a-zA-Z])[a-zA-Z]\s*=\s*[-+]?[0-9]+(?:\.[0-9]+)?(?:/[0-9]+)?", msg):
        cands.append(m.group(0))
    # führendes '= 5'
    m = re.search(r"^\s*=\s*([-+]?[0-9]+(?:\.[0-9]+)?)", msg)
    if m:
        cands.append(m.group(1))
    # eine einzelne Zahl – nur wenn die Nachricht kurz/antwortartig ist,
    # sonst matcht eine Zahl aus einer Prosa-Frage ("muss ich minus 5 rechnen?") faelschlich
    nums = re.findall(r"[-+]?[0-9]+(?:\.[0-9]+)?", msg)
    if len(nums) == 1 and not cands and len(msg.split()) <= 3:
        cands.append(nums[0])
    return cands


def _arithmetic_expression(text: str) -> str | None:
    """Reine Rechen-Aufgabe ohne «=» erkennen («2 + 4», «Berechne: 348 + 267»).

    Nur Ziffern/Operatoren/Klammern, mindestens ein Operator zwischen zwei
    Zahlen, und SymPy muss das Fragment zu einer ZAHL auswerten koennen.
    """
    msg = _normalize(text)
    label = re.match(r"^\s*[A-Za-zÀ-ÿ ]+:\s*(.+)$", msg)
    if label:
        msg = label.group(1)
    m = re.search(r"[-+]?[0-9(][0-9+\-*/^(). ]*", msg)
    if not m:
        return None
    frag = m.group(0).strip().rstrip("+-*/^(. ")
    if not re.search(r"[0-9)]\s*[+\-*/^]\s*[-+]?[0-9(]", frag):
        return None  # einzelne Zahl ist keine Aufgabe
    try:
        value = _parse(frag)
    except Exception:
        return None
    return frag if getattr(value, "is_number", False) else None


def extract_expression(text: str) -> str | None:
    """Zieht aus einem Aufgabentext eine prüfbare Gleichung («Löse 3x = 15» -> «3x = 15»).

    Wird beim Anlegen einer Aufgabe als Fallback benutzt, wenn kein expliziter
    Mathe-Ausdruck hinterlegt wurde – sonst wäre die Aufgabe nie verifizierbar.
    """
    if not text:
        return None
    if "=" not in text:
        # Reine Rechen-Aufgaben («2 + 4») sind auch ohne «=» pruefbar.
        for ln in [l for l in text.splitlines() if l.strip()] or [text]:
            found = _arithmetic_expression(ln)
            if found:
                return found
        return None
    # Mehrzeilige Eingaben (Stift/Foto-Erkennung): erst Zeile fuer Zeile
    # versuchen, dann alles zu EINER Zeile verbunden («2 + 3\n= 2y»).
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        # nur Zeilen MIT «=» einzeln probieren – sonst schnappt sich der
        # Arithmetik-Zweig die erste Zeile einer zerteilten Gleichung
        for ln in lines:
            if "=" in ln:
                found = extract_expression(ln)
                if found:
                    return found
        return extract_expression(" ".join(lines))
    # Fuehrendes Prosa-Label mit Doppelpunkt abtrennen («Berechne x: 2x+4=10»),
    # damit der Doppelpunkt nicht als Division normalisiert wird.
    label = re.match(r"^\s*[A-Za-zÀ-ÿ ]+:\s*(.+)$", text)
    if label and "=" in label.group(1):
        text = label.group(1)
    msg = _normalize(text)
    # Nicht-ASCII (ö, ü, é …) bricht den Match bewusst ab – Prosa fällt so heraus
    m = re.search(r"([0-9A-Za-z+\-*/^(). ]+)=\s*([0-9A-Za-z+\-*/^(). ]+)", msg)
    if not m:
        return None
    rhs_tokens: list[str] = []
    for t in m.group(2).split():
        if re.fullmatch(r"[A-Za-z]{2,}", t):
            break  # Prosa nach der rechten Seite kappen («… = 15 oder»)
        rhs_tokens.append(t)
    if not rhs_tokens:
        return None
    try:
        rhs = _parse(" ".join(rhs_tokens))
    except Exception:
        return None
    lhs_tokens = m.group(1).split()
    # Von links Prosa-Tokens abwerfen, bis eine loesbare Gleichung mit genau
    # einer einbuchstabigen Variablen uebrig bleibt («Berechne x wenn 2x+4 = 10»).
    # Es duerfen NUR reine Buchstaben-Woerter fallen – wird ein Mathe-Token
    # (Zahl, «3x», Operator) abgeworfen, waere die Rest-Gleichung eine ANDERE
    # Aufgabe («3x + 5 = 2y» darf nicht zu «+5 = 2y» verstuemmelt werden).
    while lhs_tokens:
        try:
            lhs = _parse(" ".join(lhs_tokens))
        except Exception:
            lhs = None
        if lhs is not None:
            syms = lhs.free_symbols | rhs.free_symbols
            if len(syms) == 1 and all(len(str(s)) == 1 for s in syms):
                if _solutions(lhs, rhs, next(iter(syms))):
                    return f"{' '.join(lhs_tokens)} = {' '.join(rhs_tokens)}"
        if not re.fullmatch(r"[A-Za-zÀ-ÿ]+", lhs_tokens[0]):
            return None  # Mathe-Token muesste fallen -> keine saubere Gleichung
        lhs_tokens.pop(0)
    return None


def _latex_to_linear(s: str) -> str:
    """Uebliche LaTeX-Formen in lineare Schreibweise fuer die Nachrechnung."""
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
    s = (s.replace(r"\cdot", "*").replace(r"\times", "*").replace(r"\div", "/")
          .replace(r"\left", "").replace(r"\right", ""))
    s = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", s)
    return s


def check_reply_math(text: str) -> list[tuple[str, str]]:
    """Rechnet rein NUMERISCHE Gleichungen in $…$-Formeln einer Tutor-Antwort nach.

    Liefert [(original_formel, richtiger_wert), …] fuer jede falsche
    Gleichung. Alles mit Variablen oder nicht Parsebares wird still
    uebersprungen – lieber ein Fehler verpasst als eine falsche Korrektur.
    """
    corrections: list[tuple[str, str]] = []
    for m in re.finditer(r"\$\$?([^$]+)\$\$?", text or ""):
        raw = m.group(1).strip()
        s = _latex_to_linear(raw)
        if "\\" in s or "=" not in s:
            continue  # unbekanntes LaTeX / keine Gleichung -> nicht pruefbar
        segments = [p.strip() for p in s.split("=")]
        if len(segments) < 2 or any(not p for p in segments):
            continue
        try:
            values = [_parse(p) for p in segments]
        except Exception:
            continue
        if not all(getattr(v, "is_number", False) for v in values):
            continue  # Variablen im Spiel -> keine reine Zahlen-Gleichung
        expected = values[0]  # erster Teil ist die Rechnung, dahinter das Resultat
        try:
            if any(sp.simplify(v - expected) != 0 for v in values[1:]):
                corrections.append((raw, str(sp.nsimplify(expected))))
        except Exception:
            continue
    return corrections


def verify(exercise_expr: str | None, message: str) -> Verification:
    """Prüft eine Schülerantwort gegen den Aufgaben-Ausdruck."""
    # Auch ohne pruefbare Aufgabe erkennen wir, OB eine Antwort versucht wurde –
    # sonst zaehlt die Hinweis-Leiter echte Versuche nicht (extracted -> intent 'attempt').
    _cands = _extract_candidates(message)
    _attempted = _cands[0] if _cands else None

    if not exercise_expr:
        return Verification("unknown", "kein Mathe-Ausdruck zur Aufgabe hinterlegt", extracted=_attempted)

    eq = _split_equation(exercise_expr)
    if eq is None:
        # Reine Rechen-Aufgabe («2 + 4»): Zahlenwert der Antwort vergleichen.
        try:
            expected = _parse(exercise_expr)
        except Exception:
            expected = None
        if expected is not None and getattr(expected, "is_number", False):
            sol_str = f"= {sp.nsimplify(expected)}"
            values = []
            for cand in _cands:
                ceq = _split_equation(cand)
                if ceq is not None:
                    values += [side for side in ceq if side.is_number]
                else:
                    try:
                        c = _parse(cand)
                        if c.is_number:
                            values.append(c)
                    except Exception:
                        pass
            if any(sp.simplify(v - expected) == 0 for v in values):
                return Verification("correct", "Zahlenwert stimmt", solution=sol_str,
                                    extracted=_attempted, score=1.0)
            if values:
                return Verification("incorrect", "Zahlenwert stimmt nicht", solution=sol_str,
                                    extracted=_attempted)
            return Verification("unknown", "keine Zahl in der Antwort erkannt",
                                solution=sol_str, extracted=_attempted)
        # Aufgabe ist keine Gleichung (z.B. Term mit Variablen) – nur grob prüfen
        return Verification("unknown", "Aufgabe ist keine Gleichung, keine deterministische Prüfung",
                            extracted=_attempted)

    lhs, rhs = eq
    sym = _free_symbol(lhs, rhs)
    if sym is None:
        return Verification("unknown", "keine Variable in der Aufgabe gefunden", extracted=_attempted)

    sols = _solutions(lhs, rhs, sym)
    sol_str = ", ".join(f"{sym} = {sp.nsimplify(s)}" for s in sols) if sols else None

    candidates = _extract_candidates(message)
    if not candidates:
        return Verification("unknown", "keine Antwort im Text erkannt", solution=sol_str)

    for cand in candidates:
        # Fall A: der/die Schüler:in nennt einen Wert für die Variable
        val_eq = _split_equation(cand)
        if val_eq is not None:
            c_lhs, c_rhs = val_eq
            # Fremd-Symbole (aus Prosa wie "ich glaube x = 5") -> kein sauberer Kandidat
            if (c_lhs.free_symbols | c_rhs.free_symbols) - {sym}:
                continue
            # Endantwort 'x = wert' – oder gespiegelt 'wert = x' («5/2 = y»)?
            value = None
            if c_lhs == sym and c_rhs.is_number:
                value = c_rhs
            elif c_rhs == sym and c_lhs.is_number:
                value = c_lhs
            if value is not None:
                for s in sols:
                    try:
                        if sp.simplify(value - s) == 0:
                            return Verification("correct", "Endwert stimmt", sol_str, cand, 1.0)
                    except Exception:
                        pass
                return Verification("incorrect", "Endwert stimmt nicht", sol_str, cand, 0.0)
            # Reines Wiederholen der Aufgabe (gleiche Seiten, evtl. vertauscht) ist
            # KEIN eigener Schritt – sonst liesse sich die Stufe-4-Sperre durch
            # zweimaliges Abtippen der Aufgabe aushebeln.
            try:
                same = sp.simplify(c_lhs - lhs) == 0 and sp.simplify(c_rhs - rhs) == 0
                swapped = sp.simplify(c_lhs - rhs) == 0 and sp.simplify(c_rhs - lhs) == 0
                if same or swapped:
                    return Verification("unknown", "nur die Aufgabe wiederholt, kein eigener Schritt",
                                        sol_str, cand)
            except Exception:
                pass
            # Umformungsschritt: gleiche Lösungsmenge wie das Original?
            try:
                c_sols = _solutions(c_lhs, c_rhs, sym)
                if c_sols and sols and set(map(sp.simplify, c_sols)) == set(map(sp.simplify, sols)):
                    return Verification("partial", "gültiger Umformungsschritt", sol_str, cand, 0.6)
            except Exception:
                pass
            return Verification("incorrect", "Umformung nicht äquivalent", sol_str, cand, 0.0)

        # Fall B: nackte Zahl -> gegen Lösungen prüfen
        try:
            val = _parse(cand)
            if val.is_number:
                for s in sols:
                    if sp.simplify(val - s) == 0:
                        return Verification("correct", "Zahl stimmt", sol_str, cand, 1.0)
                return Verification("incorrect", "Zahl stimmt nicht", sol_str, cand, 0.0)
        except Exception:
            continue

    return Verification("unknown", "Antwort nicht eindeutig prüfbar", solution=sol_str)
