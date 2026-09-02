"""Was die Hosting-Plattform ueber sich selbst verraet.

Bewusst ohne Import von ``app.config``: dieses Modul wird in ``api/index.py``
sehr frueh gebraucht – noch bevor ``DATABASE_URL`` gesetzt ist. Wuerde hier
``config`` importiert, stuende die Einstellungen-Instanz zu frueh fest und die
App liefe gegen die falsche Datenbank.
"""
from collections.abc import Mapping


def oeffentliche_basis_url(env: Mapping[str, str]) -> str | None:
    """Die Adresse, unter der Nutzer *diese* Instanz erreichen.

    Wichtig fuer Mail-Links (Anmeldung, Passwort vergessen): eine
    Vorschau-Instanz liegt unter einer eigenen Adresse. Ohne die Unterscheidung
    unten zeigten Links aus einer Vorschau auf die ECHTE Seite – ein Testlauf
    haette also die Produktion geoeffnet statt die Vorschau.

    Ausserhalb einer Vorschau bleibt das Verhalten unveraendert: erst die
    Produktions-Adresse des Projekts, dann die Adresse des Deployments.
    Liefert ``None``, wenn die Plattform gar nichts verraet (z.B. lokal) –
    dann gilt der Wert aus der Konfiguration.
    """
    if env.get("VERCEL_ENV") == "preview":
        # VERCEL_BRANCH_URL bleibt ueber alle Deploys eines Zweigs gleich und
        # ist damit die Adresse, die auch in einem Mail-Link Sinn ergibt.
        kandidaten = ("VERCEL_BRANCH_URL", "VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    else:
        kandidaten = ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL")

    for name in kandidaten:
        wert = (env.get(name) or "").strip()
        if wert:
            return f"https://{wert}"
    return None
