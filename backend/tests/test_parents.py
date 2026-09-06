"""Eltern-Verknuepfung: Code-Einloesung, Diebstahl-Schutz, Privacy-403."""
from .conftest import register


def _invite_code(client, student_headers) -> str:
    r = client.get("/api/parents/invite", headers=student_headers)
    assert r.status_code == 200
    return r.json()["invite_code"]


def test_redeem_links_parent(client):
    s = register(client, "kind@test.ch", name="Kind")
    p = register(client, "mami@test.ch", role="parent", name="Mami")
    code = _invite_code(client, s)

    r = client.post("/api/parents/redeem", headers=p, json={"invite_code": code})
    assert r.status_code == 200
    assert r.json()["student_display_name"] == "Kind"

    kids = client.get("/api/parents/children", headers=p).json()
    assert [k["student_display_name"] for k in kids] == ["Kind"]


def test_used_code_cannot_be_stolen_by_second_parent(client):
    s = register(client, "kind2@test.ch", name="Kind2")
    p1 = register(client, "mami2@test.ch", role="parent", name="Mami")
    p2 = register(client, "fremd@test.ch", role="parent", name="Fremd")
    code = _invite_code(client, s)

    assert client.post("/api/parents/redeem", headers=p1, json={"invite_code": code}).status_code == 200
    # zweiter Parent mit demselben Code -> abgelehnt, Verknuepfung von p1 bleibt
    r2 = client.post("/api/parents/redeem", headers=p2, json={"invite_code": code})
    assert r2.status_code == 400
    assert client.get("/api/parents/children", headers=p2).json() == []
    assert len(client.get("/api/parents/children", headers=p1).json()) == 1


def test_redeem_is_idempotent_for_same_parent(client):
    s = register(client, "kind3@test.ch", name="Kind3")
    p = register(client, "mami3@test.ch", role="parent", name="Mami")
    code = _invite_code(client, s)
    assert client.post("/api/parents/redeem", headers=p, json={"invite_code": code}).status_code == 200
    assert client.post("/api/parents/redeem", headers=p, json={"invite_code": code}).status_code == 200
    assert len(client.get("/api/parents/children", headers=p).json()) == 1


def test_parent_role_blocked_from_student_endpoints(client):
    p = register(client, "nurmami@test.ch", role="parent", name="Mami")
    assert client.get("/api/quota", headers=p).status_code == 403
    assert client.get("/api/attempts/1", headers=p).status_code == 403
    assert client.get("/api/topics", headers=p).status_code == 403


def test_aufgaben_ohne_thema_sind_kein_stolperstein(client):
    """Frueher landeten themenlose Aufgaben als «Ohne Thema» in den
    Stolpersteinen – und weil 80 % aller Aufgaben kein Thema haben, war das
    fast immer der erste Eintrag. Der daraus gebaute Eltern-Tipp lautete
    «Setzen Sie bei den Aufgaben ohne Thema an» und half niemandem.

    Jetzt werden sie separat gezaehlt, damit die Ansicht zur Zuordnung
    auffordern kann, statt ein Scheinproblem zu melden."""
    s = register(client, "kind3@test.ch", name="Kind3")

    ex = client.post("/api/exercises", headers=s, json={"text": "3x + 5 = 20"}).json()
    client.post(f"/api/exercises/{ex['id']}/attempts", headers=s)

    preview = client.get("/api/parents/preview", headers=s).json()
    assert [t["topic"] for t in preview["top_struggles"]] == []
    assert preview["ohne_thema"] == 1
    assert preview["worked_count"] == 1


def test_nur_hohe_hilfestufe_ist_ein_stolperstein(client):
    """«Noch nicht fertig» ist kein Stolperstein, sondern der Normalfall –
    nur 12 % aller Versuche werden ueberhaupt abgehakt. Frueher zaehlte die
    Karte «nicht geloest ODER Stufe >= 3» und faerbte damit in der Produktion
    40 von 44 Aufgaben rot."""
    from app.database import SessionLocal
    from app.models import Attempt

    s = register(client, "kind5@test.ch", name="Kind5")
    thema = client.post("/api/topics", headers=s, json={"name": "Bruchrechnen"}).json()

    ids = []
    for text in ("1/2 + 1/4", "3/4 - 1/8"):
        ex = client.post("/api/exercises", headers=s,
                         json={"text": text, "topic_id": thema["id"]}).json()
        ids.append(client.post(f"/api/exercises/{ex['id']}/attempts",
                               headers=s).json()["attempt"]["id"])

    # Beide offen, aber nur bei einer wurde wirklich viel Hilfe gebraucht.
    with SessionLocal() as db:
        db.get(Attempt, ids[0]).hint_level = 4
        db.commit()

    preview = client.get("/api/parents/preview", headers=s).json()
    entry = next(t for t in preview["top_struggles"] if t["topic"] == "Bruchrechnen")
    assert entry["heavy"] == 1, "nur die Aufgabe mit hoher Hilfe-Stufe zaehlt"
    assert entry["total"] == 2


def test_woran_gearbeitet_wurde_ohne_chat_inhalte(client):
    """Die Antwort auf die Frage, die Eltern wirklich stellen – und die Grenze:
    der Aufgabentext ja, der Chat nie."""
    s = register(client, "kind6@test.ch", name="Kind6")
    thema = client.post("/api/topics", headers=s, json={"name": "Geometrie"}).json()
    ex = client.post("/api/exercises", headers=s,
                     json={"text": "Berechne den Winkel alpha", "topic_id": thema["id"]}).json()
    client.post(f"/api/exercises/{ex['id']}/attempts", headers=s)

    preview = client.get("/api/parents/preview", headers=s).json()
    eintrag = preview["worked_on"][0]
    assert eintrag["aufgabe"] == "Berechne den Winkel alpha"
    assert eintrag["thema"] == "Geometrie"
    assert eintrag["geloest"] is False
    # Kein Feld traegt Chat-Text – die Antwort kennt nur Aufgabe und Zustand.
    assert set(eintrag) == {"aufgabe", "thema", "wann", "geloest", "viel_hilfe"}


def test_kein_trend_bei_zu_duenner_datenlage(client):
    """Gemessen an der echten Datenbank: geloeste Aufgaben pro Woche waren
    4, 0, 0, 3, 1. Der alte Vergleich meldete dabei «etwa gleich viel wie
    letzte Woche» – auch wenn letzte Woche gar nicht geuebt wurde. Jetzt gibt
    es None, und die Ansicht sagt ehrlich «zu wenig Daten»."""
    from app.services.aggregates import _trend

    assert _trend(1, None) is None      # keine Vorwoche
    assert _trend(1, 0) is None         # Vorwoche leer
    assert _trend(2, 5) is None         # diese Woche zu duenn
    assert _trend(5, 2) is None         # Vorwoche zu duenn
    assert _trend(6, 3) == 100          # genug Daten auf beiden Seiten
    assert _trend(3, 6) == -50


def test_verlauf_bleibt_erhalten(client):
    """Der Wochen-Verlauf; ohne Freigabe wird auch er genullt."""
    s = register(client, "kind4@test.ch", name="Kind4")

    for text in ("3x + 5 = 20", "2x = 10"):
        ex = client.post("/api/exercises", headers=s, json={"text": text}).json()
        client.post(f"/api/exercises/{ex['id']}/attempts", headers=s)

    preview = client.get("/api/parents/preview", headers=s).json()
    assert preview["history"], "Verlauf fehlt"
    assert preview["history"][0]["week_start"] == preview["week_start"]
    assert preview["history"][0]["worked_count"] == 2

    # Freigabe aus -> Eltern-Pfad nullt auch den Verlauf
    client.patch("/api/auth/me", headers=s, json={"share_with_parents": False})
    p = register(client, "papi4@test.ch", role="parent", name="Papi")
    code = _invite_code(client, s)
    summary = client.post("/api/parents/redeem", headers=p, json={"invite_code": code}).json()
    assert summary["shared"] is False
    assert summary["history"] == [] and summary["top_struggles"] == []
