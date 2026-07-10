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
