"""SymPy-Verifier: Endwerte, Umformungsschritte, Prosa-Robustheit."""
import pytest

from app.services.sympy_verifier import verify


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
    ],
)
def test_verify(expr, answer, expected):
    assert verify(expr, answer).status == expected


def test_solution_never_in_context():
    v = verify("3*x+5=20", "keine ahnung")
    assert v.solution == "x = 5"          # intern bekannt
    assert "solution" not in v.to_context()  # geht nie ungefiltert raus
