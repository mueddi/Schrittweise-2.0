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


def _parse(expr: str):
    return parse_expr(_normalize(expr), transformations=_TRANSFORMS, evaluate=True)


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


def extract_expression(text: str) -> str | None:
    """Zieht aus einem Aufgabentext eine prüfbare Gleichung («Löse 3x = 15» -> «3x = 15»).

    Wird beim Anlegen einer Aufgabe als Fallback benutzt, wenn kein expliziter
    Mathe-Ausdruck hinterlegt wurde – sonst wäre die Aufgabe nie verifizierbar.
    """
    if not text or "=" not in text:
        return None
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
    # einer einbuchstabigen Variablen uebrig bleibt («Berechne x wenn 2x+4 = 10»)
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
        lhs_tokens.pop(0)
    return None


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
        # Aufgabe ist keine Gleichung (z.B. reiner Term) – nur grob prüfen
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
            # Endantwort 'x = wert'?
            if c_lhs == sym and c_rhs.is_number:
                for s in sols:
                    try:
                        if sp.simplify(c_rhs - s) == 0:
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
