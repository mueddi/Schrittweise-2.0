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


def test_themenlose_aufgaben_zaehlen_als_ohne_thema(client):
    """Aufgaben ohne Thema mit viel Hilfebedarf erscheinen als Sammel-Eintrag
    «Ohne Thema» in den Stolpersteinen (statt komplett zu fehlen)."""
    s = register(client, "kind3@test.ch", name="Kind3")

    # themenlose Aufgabe, Attempt bleibt ungeloest -> Stolperstein
    ex = client.post("/api/exercises", headers=s, json={"text": "3x + 5 = 20"}).json()
    client.post(f"/api/exercises/{ex['id']}/attempts", headers=s)

    preview = client.get("/api/parents/preview", headers=s).json()
    topics = [t["topic"] for t in preview["top_struggles"]]
    assert "Ohne Thema" in topics


def test_stolpersteine_mit_zahlen_und_verlauf(client):
    """Stolpersteine tragen heavy/total, die Zusammenfassung einen
    Wochen-Verlauf; ohne Freigabe wird auch der Verlauf genullt."""
    s = register(client, "kind4@test.ch", name="Kind4")

    # zwei themenlose Aufgaben: eine ungeloest (heavy), eine nur gestartet
    for text in ("3x + 5 = 20", "2x = 10"):
        ex = client.post("/api/exercises", headers=s, json={"text": text}).json()
        client.post(f"/api/exercises/{ex['id']}/attempts", headers=s)

    preview = client.get("/api/parents/preview", headers=s).json()
    entry = next(t for t in preview["top_struggles"] if t["topic"] == "Ohne Thema")
    assert entry["heavy"] == 2 and entry["total"] == 2
    assert preview["history"], "Verlauf fehlt"
    assert preview["history"][0]["week_start"] == preview["week_start"]

    # Freigabe aus -> Eltern-Pfad nullt auch den Verlauf
    client.patch("/api/auth/me", headers=s, json={"share_with_parents": False})
    p = register(client, "papi4@test.ch", role="parent", name="Papi")
    code = _invite_code(client, s)
    summary = client.post("/api/parents/redeem", headers=p, json={"invite_code": code}).json()
    assert summary["shared"] is False
    assert summary["history"] == [] and summary["top_struggles"] == []
