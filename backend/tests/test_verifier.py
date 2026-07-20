"""SymPy-Verifier: Endwerte, Umformungsschritte, Prosa-Robustheit."""
import pytest

from app.services.sympy_verifier import extract_expression, verify


@pytest.mark.parametrize(
    "expr,answer,expected",
    [
        ("3*x + 5 = 20", "ich glaube x = 5", "correct"),
        ("3x+5=20", "x=5", "correct"),
        ("3x+5=20", "3x = 15", "partial"),          # gueltiger Umformungsschritt
        ("3x+5=20", "ich denke 3x = 15", "partial"),  # Gleichung in Prosa (Fix 6)
        ("3x+5=20", "x = 10", "incorrect"),
        ("3x+5=20", "ich weiss nicht", "unknown"),
        ("3x+5=20", "muss ich minus 5 rechnen?", "unknown"),  # Zahl in Prosa-Frage
        ("2x = 8", "4", "correct"),
        ("x^2 = 9", "x = 3", "correct"),
        ("3x+5=20", "gib mir die lösung 🙏", "unknown"),
        # gespiegelte Endantwort «wert = variable» zaehlt genauso
        ("2 + 3 = 2*y", "5/2 = y", "correct"),
        ("2 + 3 = 2*y", "5/2=y", "correct"),
        ("2 + 3 = 2*y", "3 = y", "incorrect"),
    ],
)
def test_verify(expr, answer, expected):
    assert verify(expr, answer).status == expected


def test_extract_expression_multiline():
    """Stift-/Foto-Eingaben sind oft mehrzeilig – die Gleichung muss trotzdem
    gefunden werden, sonst ist die Aufgabe nie als geloest erkennbar."""
    assert extract_expression("2 + 3\n= 2 * y") is not None
    assert verify(extract_expression("2 + 3\n= 2 * y"), "y = 5/2").status == "correct"
    # mehrere Zeilen mit eigener Gleichung: die erste loesbare gewinnt
    assert extract_expression("Löse nach x auf:\n3x + 5 = 20") == "3x + 5 = 20"


def test_solution_never_in_context():
    v = verify("3*x+5=20", "keine ahnung")
    assert v.solution == "x = 5"          # intern bekannt
    assert "solution" not in v.to_context()  # geht nie ungefiltert raus


def test_reine_rechenaufgabe_wird_erkannt_und_geprueft():
    """«2 + 4» ist auch ohne Gleichheitszeichen pruefbar."""
    from app.services.sympy_verifier import extract_expression, verify

    assert extract_expression("2 + 4") == "2 + 4"
    assert extract_expression("Berechne: 348 + 267") is not None
    assert extract_expression("Erkläre mir Brüche") is None
    assert extract_expression("42") is None  # einzelne Zahl ist keine Aufgabe

    assert verify("2 + 4", "= 6").status == "correct"
    assert verify("2 + 4", "6").status == "correct"
    assert verify("2 + 4", "2 + 4 = 6").status == "correct"
    v = verify("2 + 4", "7")
    assert v.status == "incorrect"
    assert v.solution == "= 6"
    assert verify("2 + 4", "keine ahnung").status == "unknown"


def test_lineare_schreibweise_von_links_nach_rechts():
    """Schul-Lesart: «3/2y» = (3/2)·y, nicht 3/(2y); Klassiker bleibt korrekt."""
    from app.services.sympy_verifier import verify

    # (3/2)·y = 6  ->  y = 4
    assert verify("3/2y = 6", "y = 4").status == "correct"
    assert verify("3/2y = 6", "y = 9").status == "incorrect"
    # explizite Klammern unveraendert korrekt
    assert verify("(3/2)*x = 6", "x = 4").status == "correct"
    # Regression: impliziertes Mal in Koeffizienten bleibt richtig
    assert verify("3x + 5 = 20", "x = 5").status == "correct"
    assert verify("2(x + 1) = 8", "x = 3").status == "correct"
