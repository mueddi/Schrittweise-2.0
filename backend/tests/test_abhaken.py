"""Eine fertige Aufgabe muss auch als fertig dastehen.

Gemeldet vom Betreiber: «es zeigt aufgaben nicht als beendet an obwohl sie
fertig sind». In der Produktion belegt: von 46 Aufgaben hatten 31 (67 %)
keinen Pruefausdruck – und «geloest» konnte NUR aus der SymPy-Pruefung
kommen. Diese Aufgaben liessen sich damit nie abschliessen, egal was das Kind
rechnete. Der letzte Haken in der Datenbank stammte vom 11. Juli.

Zwei Wege sind neu, und beide werden hier gefahren:
* der Tutor haengt ``[[GELOEST]]`` an, wenn das Kind fertig ist;
* das Kind hakt selbst ab (kostet nichts, geht immer).
"""
from app.routers.attempts import GELOEST_MARKER, _marker_teilen
from app.services import tutor
from app.services.sympy_verifier import extract_expression

from .test_library import register_pw


# ---------------------------------------------------------------- Marker

def test_marker_wird_nie_angezeigt():
    raus, rest, gesehen = _marker_teilen("Stark, das stimmt! [[GELOEST]]")
    assert gesehen is True
    assert GELOEST_MARKER not in raus and rest == ""
    assert raus == "Stark, das stimmt! "


def test_marker_ueber_zwei_haeppchen_verteilt():
    """Beim Streamen kommt der Marker zerteilt an – er darf trotzdem nicht
    im Chat auftauchen und muss erkannt werden."""
    raus1, rest, g1 = _marker_teilen("Fertig! [[GEL")
    assert raus1 == "Fertig! " and rest == "[[GEL" and g1 is False
    raus2, rest2, g2 = _marker_teilen(rest + "OEST]]")
    assert raus2 == "" and rest2 == "" and g2 is True


def test_eckige_klammern_im_text_bleiben_stehen():
    raus, rest, gesehen = _marker_teilen("Die Menge [1, 2] ist gemeint.")
    assert raus == "Die Menge [1, 2] ist gemeint." and rest == "" and gesehen is False


# ------------------------------------------------------------ Tutor-Weg

def _mit_antwort(client, monkeypatch, antwort: str, aufgabe: str, mail: str):
    from app.services import tutor

    def fake_stream(*args, **kwargs):
        # in zwei Haeppchen, damit der Marker wirklich zerteilt ankommt
        mitte = len(antwort) // 2
        yield antwort[:mitte]
        yield antwort[mitte:]

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, mail)
    ex = client.post("/api/exercises", headers=headers, json={"text": aufgabe}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "x = y/2"}) as r:
        sichtbar = "".join(r.iter_text())
    zustand = client.get(f"/api/attempts/{aid}", headers=headers).json()
    return headers, aid, sichtbar, zustand


def test_tutor_hakt_unpruefbare_aufgabe_ab(client, monkeypatch):
    """Der Fall aus der Produktion: «2*x = y», kein Pruefausdruck moeglich."""
    _, _, sichtbar, zustand = _mit_antwort(
        client, monkeypatch, "Stark! Genau das ist die Lösung. [[GELOEST]]",
        "2*x = y", "abhaken1@test.ch")
    assert "GELOEST" not in sichtbar          # nie im Chat sichtbar
    assert "[[" not in sichtbar
    assert zustand["attempt"]["solved"] is True
    assert all("GELOEST" not in m["text"] for m in zustand["messages"])


def test_ohne_marker_bleibt_die_aufgabe_offen(client, monkeypatch):
    _, _, _, zustand = _mit_antwort(
        client, monkeypatch, "Guter Anfang – wie geht es weiter?",
        "2*x = y", "abhaken2@test.ch")
    assert zustand["attempt"]["solved"] is False


def test_sympy_schlaegt_den_tutor(client, monkeypatch):
    """Sagt die Pruefung «falsch», darf das Modell die Aufgabe NICHT abhaken.

    Sonst koennte eine hoefliche Antwort eine falsche Loesung richtigreden.
    """
    from app.services import tutor

    def fake_stream(*args, **kwargs):
        yield "Ja super, das stimmt! [[GELOEST]]"

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "abhaken3@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x = 15"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "x = 7"}) as r:       # falsch, richtig waere 5
        "".join(r.iter_text())
    zustand = client.get(f"/api/attempts/{aid}", headers=headers).json()
    assert zustand["attempt"]["solved"] is False


def test_betteln_hakt_nie_ab(client, monkeypatch):
    """«Zeig mir die Lösung» darf die Aufgabe NICHT abschliessen.

    Gemeldet vom Betreiber und in der Produktion belegt (Aufgabe 48): die
    selbst gerechnete Lösung blieb offen, und erst der Knopf «Zeig mir die
    Lösung» hakte ab. Auf DIESER Runde liefert der Tutor die Lösung – das
    Kind hat nichts gelöst.
    """
    from app.services import tutor

    def fake_stream(*args, **kwargs):
        yield "Klar, hier der ganze Weg: $x = 5$. [[GELOEST]]"

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "abhaken9@test.ch")
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "zeichne eine Parabel"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "Zeig mir die Lösung bitte."}) as r:
        sichtbar = "".join(r.iter_text())
    assert "GELOEST" not in sichtbar
    zustand = client.get(f"/api/attempts/{aid}", headers=headers).json()
    assert zustand["attempt"]["solved"] is False


def test_regie_verlangt_die_entscheidung_beim_eigenen_schritt():
    """Der Widerspruch, der die Ursache war: die Regie nannte JEDE eigene
    Rechnung einen «Schritt» und die Abhak-Regel verbietet den Marker nach
    einem Zwischenschritt. Das Modell hielt die fertige Lösung deshalb für
    einen Zwischenschritt."""
    from app.services import tutor
    from app.services.sympy_verifier import Verification

    unpruefbar = Verification(status="unknown", detail="", extracted="7y/3", solution=None)
    schritt = tutor.LadderStep("step", 2, 1, False, False)
    regie = tutor._regie(schritt, unpruefbar, "2 + 5 = (3*x)/y", None)
    assert "VOLLSTAENDIGE Loesung" in regie
    assert regie.count("[[GELOEST]]") >= 1
    assert "zum naechsten Schritt ermutigen" in regie  # der Normalfall bleibt

    # Bei einer Bettelei darf die Abhak-Frage NICHT dastehen
    bettelt = tutor.LadderStep("plea", 4, 2, False, True)
    assert "[[GELOEST]]" not in tutor._regie(bettelt, unpruefbar, "2 + 5 = (3*x)/y", None)


# ------------------------------------------- «Ich bin fertig» sagen (statt drücken)

def test_fertig_wird_erkannt_auch_auf_mundart_und_englisch():
    for satz in ["fertig", "ich bin fertig", "das wars", "das war's", "han es",
                 "ich habs", "done", "I'm done", "finished"]:
        assert tutor.sagt_fertig(satz), satz


def test_verneintes_fertig_zaehlt_nicht():
    """«Ich bin noch nicht fertig» darf die Aufgabe nicht abschliessen."""
    for satz in ["ich bin noch nicht fertig", "bin nöd fertig", "noch nicht fertig",
                 "fertig bin ich nicht"]:
        assert not tutor.sagt_fertig(satz), satz


def test_fertig_ist_weder_versuch_noch_hilferuf():
    from app.services.sympy_verifier import Verification

    unbekannt = Verification("unknown", "", None)
    assert tutor.detect_intent("ich bin fertig", unbekannt) == "fertig"
    # Stufe und Versuchszaehler bleiben unangetastet – «fertig» ist eine
    # Behauptung, kein gerechneter Schritt.
    schritt = tutor.advance_ladder(2, 1, "fertig")
    assert (schritt.allowed_stage, schritt.own_attempts, schritt.solved) == (2, 1, False)


def test_regie_laesst_den_tutor_pruefen_statt_glauben():
    from app.services.sympy_verifier import Verification

    schritt = tutor.advance_ladder(2, 1, "fertig")
    regie = tutor._regie(schritt, Verification("unknown", "", None), "zeichne eine Parabel", None)
    assert "sagt, er sei FERTIG" in regie
    assert "hak NICHT ab" in regie          # nicht auf Zuruf
    assert "[[GELOEST]]" in regie           # aber abhaken, wenn es stimmt


def test_fertig_sagen_schliesst_ab_wenn_der_tutor_zustimmt(client, monkeypatch):
    def fake_stream(*args, **kwargs):
        yield "Stimmt, deine Gerade und die Gleichung passen zusammen. [[GELOEST]]"

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "fertig1@test.ch")
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "zeichne eine lineare Gleichung"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "ich bin fertig"}) as r:
        sichtbar = "".join(r.iter_text())
    assert "GELOEST" not in sichtbar
    assert client.get(f"/api/attempts/{aid}", headers=headers).json()["attempt"]["solved"] is True


def test_fertig_sagen_allein_reicht_nicht(client, monkeypatch):
    """Sagt der Tutor «da fehlt noch was», bleibt die Aufgabe offen."""
    def fake_stream(*args, **kwargs):
        yield "Fast! Die Gerade steht, aber die Gleichung dazu fehlt noch."

    monkeypatch.setattr(tutor, "stream_reply", fake_stream)
    headers = register_pw(client, "fertig2@test.ch")
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "zeichne eine lineare Gleichung"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "fertig"}) as r:
        "".join(r.iter_text())
    assert client.get(f"/api/attempts/{aid}", headers=headers).json()["attempt"]["solved"] is False


# -------------------------------------------------------------- Hand-Weg

def test_kind_kann_selbst_abhaken(client):
    headers = register_pw(client, "abhaken4@test.ch")
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "zeichne eine lineare Gleichung"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]

    a = client.post(f"/api/attempts/{aid}/geloest", headers=headers).json()
    assert a["solved"] is True
    # und wieder zurueck – ein Fehlgriff darf nicht endgueltig sein
    a = client.post(f"/api/attempts/{aid}/offen", headers=headers).json()
    assert a["solved"] is False


def test_hand_haken_laesst_die_hilfe_stufe_in_ruhe(client):
    """hint_level/own_attempts sind die Kennzahl «wieviel Hilfe war noetig».
    Ein Haken sagt darueber nichts – er darf sie nicht faelschen."""
    headers = register_pw(client, "abhaken5@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "male ein Dreieck"}).json()
    vorher = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]
    nachher = client.post(f"/api/attempts/{vorher['id']}/geloest", headers=headers).json()
    assert nachher["hint_level"] == vorher["hint_level"]
    assert nachher["own_attempts"] == vorher["own_attempts"]


def test_fremde_aufgabe_nicht_abhakbar(client):
    a = register_pw(client, "abhaken6@test.ch")
    b = register_pw(client, "abhaken7@test.ch")
    ex = client.post("/api/exercises", headers=a, json={"text": "male ein Dreieck"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=a).json()["attempt"]["id"]
    assert client.post(f"/api/attempts/{aid}/geloest", headers=b).status_code == 404


def test_abgehakte_aufgabe_zaehlt_im_thema(client):
    """Der Zaehler «x/y gelöst» auf der Themen-Karte muss mitziehen."""
    headers = register_pw(client, "abhaken8@test.ch")
    topic = client.post("/api/topics", headers=headers, json={"name": "Zeichnen"}).json()
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "zeichne eine Parabel", "topic_id": topic["id"]}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    assert client.get("/api/topics", headers=headers).json()[0]["solved_count"] == 0
    client.post(f"/api/attempts/{aid}/geloest", headers=headers)
    assert client.get("/api/topics", headers=headers).json()[0]["solved_count"] == 1


# ------------------------------------------------------- Pruefausdruck

def test_aufgabe_mit_gleichheitszeichen_am_ende_ist_pruefbar():
    """«2 + 7 =» ist die normale Schreibweise auf dem Papier. Vorher bekam
    sie keinen Pruefausdruck und war deshalb nie loesbar."""
    assert extract_expression("2 + 7 =") == "2 + 7"
    assert extract_expression("348 + 267 = ") == "348 + 267"
    # und die bisherigen Faelle bleiben, wie sie waren
    assert extract_expression("3x + 5 = 20") == "3x + 5 = 20"
    assert extract_expression("x =") is None
