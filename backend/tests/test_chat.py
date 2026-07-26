

def test_abgeschnittener_figur_block_kommt_nicht_in_den_verlauf():
    """Bricht die Antwort mitten in einer Skizze ab, wurde der Torso
    gespeichert – und der Verlauf zeigte danach bei JEDEM Laden rohes JSON."""
    from app.routers.attempts import _ohne_offenen_figur_block as ohne

    assert ohne('Schau mal: [[FIGUR]]{"typ":"waage","links":"3x + 5') == "Schau mal:"
    # vollstaendige Bloecke bleiben unangetastet
    ganz = 'Schau: [[FIGUR]]{"typ":"bruch"}[[/FIGUR]] und weiter'
    assert ohne(ganz) == ganz
    assert ohne("ganz normaler Text") == "ganz normaler Text"
