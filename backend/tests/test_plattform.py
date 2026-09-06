"""Welche Adresse die App fuer Mail-Links benutzt.

Der Fehler, den diese Tests festhalten: eine Vorschau-Instanz verschickte
Links auf die ECHTE Seite. Wer in der Vorschau eine Registrierung
durchspielte, landete beim Klick auf die Mail in der Produktion.
"""
from app.plattform import oeffentliche_basis_url, vorschau_defaults


PRODUKTION = "schrittweise-2-0.vercel.app"
ZWEIG = "schrittweise-2-0-git-mein-zweig-mahmmoud-said.vercel.app"
DEPLOYMENT = "schrittweise-2-0-7bh8v7uza-mahmmoud-said.vercel.app"


def test_vorschau_verlinkt_auf_sich_selbst_nicht_auf_die_echte_seite():
    """Der eigentliche Fix."""
    adresse = oeffentliche_basis_url({
        "VERCEL_ENV": "preview",
        "VERCEL_BRANCH_URL": ZWEIG,
        "VERCEL_URL": DEPLOYMENT,
        "VERCEL_PROJECT_PRODUCTION_URL": PRODUKTION,
    })
    assert adresse == f"https://{ZWEIG}"
    assert PRODUKTION not in adresse


def test_vorschau_ohne_zweig_adresse_nimmt_die_des_deployments():
    adresse = oeffentliche_basis_url({
        "VERCEL_ENV": "preview",
        "VERCEL_URL": DEPLOYMENT,
        "VERCEL_PROJECT_PRODUCTION_URL": PRODUKTION,
    })
    assert adresse == f"https://{DEPLOYMENT}"


def test_produktion_bleibt_unveraendert():
    """Gegenprobe: am Verhalten der echten Seite darf sich NICHTS aendern –
    auch dann nicht, wenn Vercel eine Zweig-Adresse mitschickt."""
    adresse = oeffentliche_basis_url({
        "VERCEL_ENV": "production",
        "VERCEL_BRANCH_URL": ZWEIG,
        "VERCEL_URL": DEPLOYMENT,
        "VERCEL_PROJECT_PRODUCTION_URL": PRODUKTION,
    })
    assert adresse == f"https://{PRODUKTION}"


def test_ohne_vercel_env_gilt_die_alte_regel():
    """Der Deploy aus dem GitHub-Ablauf ist ebenfalls Produktion. Selbst wenn
    VERCEL_ENV fehlen sollte, darf nie die Deployment-Adresse gewinnen."""
    adresse = oeffentliche_basis_url({
        "VERCEL_URL": DEPLOYMENT,
        "VERCEL_PROJECT_PRODUCTION_URL": PRODUKTION,
    })
    assert adresse == f"https://{PRODUKTION}"


def test_lokal_verraet_die_plattform_nichts():
    """Ohne Vercel-Variablen bleibt es beim Wert aus der Konfiguration."""
    assert oeffentliche_basis_url({}) is None
    assert oeffentliche_basis_url({"VERCEL_URL": "   "}) is None


# --- Sonderregeln der Vorschau ---
def test_vorschau_verlangt_keine_mail_bestaetigung():
    """Sonst ist die Vorschau eine Sackgasse: leere Datenbank, also neu
    registrieren – und dann auf eine Mail warten, die dort nie ankommt."""
    assert vorschau_defaults({"VERCEL_ENV": "preview"}) == {
        "REQUIRE_EMAIL_VERIFICATION": "false"
    }


def test_die_echte_seite_bekommt_keine_sonderregeln():
    """Gegenprobe – der wichtigste Test der beiden."""
    assert vorschau_defaults({"VERCEL_ENV": "production"}) == {}
    assert vorschau_defaults({}) == {}
    assert vorschau_defaults({"VERCEL_ENV": "development"}) == {}
