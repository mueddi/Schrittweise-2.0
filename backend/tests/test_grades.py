"""Schulnoten: Grenzen der Skala, Besitz, Verlauf und Trend."""
from datetime import date, timedelta

from .conftest import register


def _thema(client, headers, name="Bruchrechnen"):
    return client.post("/api/topics", headers=headers, json={"name": name}).json()["id"]


def test_note_anlegen_und_lesen(client):
    headers = register(client, "noten@test.ch")
    tid = _thema(client, headers)
    r = client.post("/api/grades", headers=headers,
                    json={"value": 4.5, "taken_on": "2026-06-01", "topic_id": tid,
                          "label": "Prüfung Brüche"})
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["value"] == 4.5
    assert note["source"] == "selbst"      # nicht aus einer Probepruefung
    assert note["exam_id"] is None

    # Die Liste steht im Verlauf – eine zweite, inhaltsgleiche Liste unter
    # GET /api/grades gab es frueher, sie wurde von der App nie geholt.
    liste = client.get("/api/grades/verlauf", headers=headers).json()["noten"]
    assert len(liste) == 1
    # Filter nach Thema
    assert len(client.get(f"/api/grades/verlauf?topic_id={tid}", headers=headers).json()["noten"]) == 1
    assert client.get("/api/grades/verlauf?topic_id=999999", headers=headers).json()["noten"] == []


def test_skala_grenzen(client):
    """Schweizer Skala 1.0–6.0. Daneben darf nichts durchkommen – eine Note
    ausserhalb wuerde jeden Schnitt und jeden Trend verfaelschen."""
    headers = register(client, "grenzen@test.ch")
    for wert in [0.9, 6.1, -3, 60]:
        r = client.post("/api/grades", headers=headers,
                        json={"value": wert, "taken_on": "2026-06-01"})
        assert r.status_code == 422, f"{wert} haette abgewiesen werden muessen"
    for wert in [1.0, 4.0, 6.0]:
        r = client.post("/api/grades", headers=headers,
                        json={"value": wert, "taken_on": "2026-06-01"})
        assert r.status_code == 201, f"{wert} ist gueltig"


def test_datum_in_der_zukunft_abgewiesen(client):
    """Eine Pruefung, die noch nicht war, kann keine Note haben."""
    headers = register(client, "zukunft@test.ch")
    morgen = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/api/grades", headers=headers, json={"value": 5.0, "taken_on": morgen})
    assert r.status_code == 400
    assert "Zukunft" in r.json()["detail"]


def test_fremde_note_und_fremdes_thema_unerreichbar(client):
    """404 statt 403: fremde IDs sollen nicht einmal bestaetigt werden."""
    a = register(client, "a@test.ch")
    b = register(client, "b@test.ch")
    tid_a = _thema(client, a)
    note_a = client.post("/api/grades", headers=a,
                         json={"value": 5.0, "taken_on": "2026-06-01"}).json()["id"]

    assert client.delete(f"/api/grades/{note_a}", headers=b).status_code == 404
    # fremdes Thema referenzieren
    r = client.post("/api/grades", headers=b,
                    json={"value": 5.0, "taken_on": "2026-06-01", "topic_id": tid_a})
    assert r.status_code == 404
    # B sieht die Note von A gar nicht
    assert client.get("/api/grades/verlauf", headers=b).json()["noten"] == []


def test_note_loeschen(client):
    """Korrigieren heisst loeschen und neu eintragen – einen Aender-Weg gibt es
    bewusst nicht mehr (er hatte nie einen Knopf in der App)."""
    headers = register(client, "aendern@test.ch")
    nid = client.post("/api/grades", headers=headers,
                      json={"value": 3.5, "taken_on": "2026-06-01"}).json()["id"]
    assert client.delete(f"/api/grades/{nid}", headers=headers).status_code == 204
    assert client.get("/api/grades/verlauf", headers=headers).json()["noten"] == []


def test_verlauf_schnitt_und_trend(client):
    """Der Trend ist die Zahl, die Eltern lesen – er muss stimmen und darf bei
    Rauschen NICHT anschlagen."""
    headers = register(client, "verlauf@test.ch")
    for tag, wert in [("2026-03-01", 3.0), ("2026-04-01", 3.5),
                      ("2026-05-01", 5.0), ("2026-06-01", 5.5)]:
        client.post("/api/grades", headers=headers, json={"value": wert, "taken_on": tag})

    v = client.get("/api/grades/verlauf", headers=headers).json()
    assert [n["value"] for n in v["noten"]] == [3.0, 3.5, 5.0, 5.5]  # aelteste zuerst
    assert v["schnitt"] == 4.25
    assert v["trend"] == "besser"
    assert v["bestanden_anteil"] == 0.5   # 2 von 4 Noten >= 4.0


def test_verlauf_kleine_schwankung_ist_kein_trend(client):
    headers = register(client, "rauschen@test.ch")
    for tag, wert in [("2026-05-01", 4.0), ("2026-06-01", 4.1)]:
        client.post("/api/grades", headers=headers, json={"value": wert, "taken_on": tag})
    assert client.get("/api/grades/verlauf", headers=headers).json()["trend"] == "gleich"


def test_verlauf_ohne_noten(client):
    headers = register(client, "leer@test.ch")
    v = client.get("/api/grades/verlauf", headers=headers).json()
    assert v["noten"] == [] and v["schnitt"] is None and v["bestanden_anteil"] is None


def test_eltern_duerfen_keine_noten_schreiben(client):
    """Noten sind die Angabe des Kindes. Eltern lesen sie im Dashboard mit,
    schreiben aber nie – sonst waere die Zahl nicht mehr die des Kindes."""
    eltern = register(client, "mama@test.ch", role="parent")
    r = client.post("/api/grades", headers=eltern,
                    json={"value": 5.0, "taken_on": "2026-06-01"})
    assert r.status_code == 403
    assert client.get("/api/grades/verlauf", headers=eltern).status_code == 403


# ---- Archivieren statt Löschen (Teil B) ----

def test_archivieren_versteckt_das_thema_aber_nichts_geht_verloren(client):
    headers = register(client, "archiv@test.ch")
    tid = _thema(client, headers, "Fertiges Thema")
    client.post("/api/grades", headers=headers,
                json={"value": 5.0, "taken_on": "2026-06-01", "topic_id": tid})

    r = client.post(f"/api/topics/{tid}/archivieren", headers=headers)
    assert r.status_code == 200 and r.json()["archived_at"] is not None

    # Aus der normalen Liste (= Seitenleiste UND Raster) verschwunden …
    assert [t["id"] for t in client.get("/api/topics", headers=headers).json()] == []
    # … aber im Archiv da, mit den Noten
    archiv = client.get("/api/topics?archiviert=true", headers=headers).json()
    assert [t["id"] for t in archiv] == [tid]
    assert archiv[0]["grade_count"] == 1 and archiv[0]["grade_avg"] == 5.0

    # Wiederherstellen bringt es zurück
    assert client.post(f"/api/topics/{tid}/wiederherstellen", headers=headers).status_code == 200
    assert [t["id"] for t in client.get("/api/topics", headers=headers).json()] == [tid]


def test_loeschen_mit_noten_wird_erst_abgelehnt(client):
    """Eine Notenhistorie ist nicht wiederherstellbar – ein Klick aus Versehen
    darf sie nicht vernichten."""
    headers = register(client, "loeschschutz@test.ch")
    tid = _thema(client, headers)
    client.post("/api/grades", headers=headers,
                json={"value": 4.0, "taken_on": "2026-06-01", "topic_id": tid})

    r = client.delete(f"/api/topics/{tid}", headers=headers)
    assert r.status_code == 409
    assert "Archiviere" in r.json()["detail"]
    # Thema ist noch da
    assert [t["id"] for t in client.get("/api/topics", headers=headers).json()] == [tid]


def test_loeschen_trotzdem_behaelt_die_noten(client):
    """Wer wirklich loescht, verliert das Thema – aber NIE die Noten."""
    headers = register(client, "trotzdem@test.ch")
    tid = _thema(client, headers)
    client.post("/api/grades", headers=headers,
                json={"value": 4.0, "taken_on": "2026-06-01", "topic_id": tid})
    client.post("/api/grades", headers=headers,
                json={"value": 5.0, "taken_on": "2026-06-08", "topic_id": tid})

    assert client.delete(f"/api/topics/{tid}?trotzdem=true", headers=headers).status_code == 204
    assert client.get("/api/topics", headers=headers).json() == []
    noten = client.get("/api/grades/verlauf", headers=headers).json()["noten"]
    assert len(noten) == 2, "die Noten muessen erhalten bleiben"
    assert all(n["topic_id"] is None for n in noten)
    # und der Gesamt-Verlauf stimmt weiterhin
    assert client.get("/api/grades/verlauf", headers=headers).json()["schnitt"] == 4.5


def test_loeschen_ohne_noten_geht_direkt(client):
    """Ohne Noten gibt es nichts zu schuetzen – kein laestiges Nachfragen."""
    headers = register(client, "leerloeschen@test.ch")
    tid = _thema(client, headers)
    assert client.delete(f"/api/topics/{tid}", headers=headers).status_code == 204


def test_lernziele_speicherbar(client):
    """Grundlage der Probepruefung – ohne Ziele kann sie nichts erzeugen."""
    headers = register(client, "ziele@test.ch")
    tid = _thema(client, headers)
    ziele = "Brüche kürzen\nBrüche addieren\ngemischte Zahlen umwandeln"
    r = client.patch(f"/api/topics/{tid}", headers=headers, json={"learning_goals": ziele})
    assert r.status_code == 200
    assert r.json()["learning_goals"] == ziele
