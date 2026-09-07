"""Probeprüfung: Erzeugen, Korrigieren, Kosten – und was NICHT passieren darf."""
import json
import types

from app.config import settings
from app.services import exam as exam_service, quota

from .conftest import register

# Was das Modell zurückgibt. Bewusst gemischt: brauchbare Prüfausdrücke,
# ein UNBRAUCHBARER (der verworfen werden muss) und einer ohne Ausdruck.
MODELL_ANTWORT = json.dumps([
    {"frage": "Löse: 3x = 15", "ausdruck": "3x = 15", "ziel": "Gleichungen lösen"},
    {"frage": "Löse: x + 7 = 12", "ausdruck": "x + 7 = 12", "ziel": "Gleichungen lösen"},
    {"frage": "Berechne 24 + 18", "ausdruck": "24 + 18", "ziel": "Kopfrechnen"},
    {"frage": "Wie viel ist 2x = 10?", "ausdruck": "2x = 10", "ziel": "Gleichungen lösen"},
    # Der Tuersteher muss diesen verwerfen: loest nur symbolisch auf
    {"frage": "Stelle y frei: 3x + 5 = 2y", "ausdruck": "3x + 5 = 2y", "ziel": "Umformen"},
    # Ohne Ausdruck: von Hand/nicht bewertbar
    {"frage": "Zeichne ein Dreieck und beschrifte die Seiten.", "ausdruck": "",
     "ziel": "Geometrie"},
], ensure_ascii=False)


def _fake_anthropic(text=MODELL_ANTWORT, fehler=None, aufrufe=None, calls=None):
    class _Messages:
        def create(self, **kwargs):
            if aufrufe is not None:
                aufrufe.append(kwargs.get("model"))
            if calls is not None:
                calls.append(kwargs)          # vollstaendige Parameter mitschneiden
            if fehler:
                raise fehler
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=text)],
                usage=types.SimpleNamespace(input_tokens=1500, output_tokens=1300,
                                            cache_read_input_tokens=0,
                                            cache_creation_input_tokens=0),
            )

    class _Client:
        def __init__(self, api_key, **kwargs):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Client)


def _thema_mit_zielen(client, headers, ziele="Gleichungen lösen\nKopfrechnen\nUmformen"):
    tid = client.post("/api/topics", headers=headers, json={"name": "Algebra"}).json()["id"]
    client.patch(f"/api/topics/{tid}", headers=headers, json={"learning_goals": ziele})
    return tid


def _mit_ki(monkeypatch, **kw):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(exam_service, "anthropic", _fake_anthropic(**kw))


# ---- Vorschau: kostet nichts, sagt den Preis ----

def test_vorschau_ohne_lernziele_ist_nicht_moeglich(client):
    headers = register(client, "vorschau1@test.ch")
    tid = client.post("/api/topics", headers=headers, json={"name": "Leer"}).json()["id"]
    v = client.post(f"/api/topics/{tid}/pruefung/vorschau", headers=headers).json()
    assert v["moeglich"] is False
    assert "Lernziele" in v["grund"]


def test_vorschau_nennt_den_preis_vorher(client):
    """Bei 50 Gratis-Tokens im Monat ist eine Pruefung ein spuerbarer Teil des
    Budgets – der Preis muss VOR dem Klick dastehen."""
    headers = register(client, "vorschau2@test.ch")
    tid = _thema_mit_zielen(client, headers)
    v = client.post(f"/api/topics/{tid}/pruefung/vorschau", headers=headers).json()
    assert v["moeglich"] is True
    assert v["lernziele"] == 3
    assert v["kosten_rappen"] > 0
    assert v["guthaben"] == 50


# ---- Erzeugen ----

def test_pruefung_wird_erzeugt_und_unbrauchbarer_ausdruck_verworfen(client, monkeypatch):
    """Der Fehler von heute Morgen darf nicht zurueckkommen: ein Ausdruck, der
    nur symbolisch aufloest, darf NICHT als Pruefausdruck gespeichert werden –
    sonst gilt die richtige Antwort spaeter als falsch."""
    headers = register(client, "erzeugen@test.ch")
    tid = _thema_mit_zielen(client, headers)
    _mit_ki(monkeypatch)

    r = client.post(f"/api/topics/{tid}/pruefung", headers=headers)
    assert r.status_code == 201, r.text
    pruefung = r.json()
    assert pruefung["status"] == "offen"
    assert len(pruefung["items"]) == 6
    assert pruefung["items"][0]["question"].startswith("Löse")
    assert pruefung["items"][0]["goal"] == "Gleichungen lösen"

    from app.database import SessionLocal
    from app.models import ExamItem

    with SessionLocal() as db:
        items = db.query(ExamItem).order_by(ExamItem.position).all()
        # «3x + 5 = 2y» loest nur symbolisch auf -> kein Pruefausdruck
        assert items[4].math_expression == ""
        # «Zeichne ein Dreieck» hatte gar keinen
        assert items[5].math_expression == ""
        # die brauchbaren sind da
        assert items[0].math_expression and items[2].math_expression


def test_erzeugen_bucht_ab_und_erfasst_die_nutzung(client, monkeypatch):
    headers = register(client, "kosten@test.ch")
    tid = _thema_mit_zielen(client, headers)
    _mit_ki(monkeypatch)
    vorher = client.get("/api/quota", headers=headers).json()["remaining"]

    client.post(f"/api/topics/{tid}/pruefung", headers=headers)

    from app.database import SessionLocal
    from app.models import ApiUsage

    with SessionLocal() as db:
        zeilen = db.query(ApiUsage).filter(ApiUsage.kind == "pruefung").all()
        assert len(zeilen) == 1
        assert zeilen[0].charged_tokens > 0
    assert client.get("/api/quota", headers=headers).json()["remaining"] < vorher


def test_ausfall_kostet_nichts_und_speichert_keine_halbe_pruefung(client, monkeypatch):
    headers = register(client, "ausfall@test.ch")
    tid = _thema_mit_zielen(client, headers)
    _mit_ki(monkeypatch, fehler=RuntimeError("api down"))

    r = client.post(f"/api/topics/{tid}/pruefung", headers=headers)
    assert r.status_code == 503
    assert "nichts abgebucht" in r.json()["detail"]
    assert client.get("/api/quota", headers=headers).json()["remaining"] == 50
    assert client.get(f"/api/topics/{tid}/pruefungen", headers=headers).json() == []


def test_ueberlastetes_modell_weicht_aus(client, monkeypatch):
    """Eine Pruefung darf nicht an einem ueberlasteten Modell scheitern."""
    headers = register(client, "ausweich@test.ch")
    tid = _thema_mit_zielen(client, headers)
    aufrufe = []
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    class _Messages:
        def create(self, **kwargs):
            aufrufe.append(kwargs.get("model"))
            if len(aufrufe) == 1:
                raise RuntimeError("overloaded")
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=MODELL_ANTWORT)],
                usage=types.SimpleNamespace(input_tokens=1500, output_tokens=1300,
                                            cache_read_input_tokens=0,
                                            cache_creation_input_tokens=0))

    class _Client:
        def __init__(self, api_key, **kwargs):
            self.messages = _Messages()

    monkeypatch.setattr(exam_service, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    assert client.post(f"/api/topics/{tid}/pruefung", headers=headers).status_code == 201
    assert len(aufrufe) == 2, "es muss auf das andere Modell gewechselt werden"
    assert aufrufe[0] != aufrufe[1]


def test_ohne_lernziele_kein_modellaufruf(client, monkeypatch):
    headers = register(client, "keineziele@test.ch")
    tid = client.post("/api/topics", headers=headers, json={"name": "Leer"}).json()["id"]
    aufrufe = []
    _mit_ki(monkeypatch, aufrufe=aufrufe)
    r = client.post(f"/api/topics/{tid}/pruefung", headers=headers)
    assert r.status_code == 400
    assert aufrufe == [], "ohne Lernziele darf gar kein Modell laufen"


def test_leeres_guthaben_blockt_vor_dem_modellaufruf(client, monkeypatch):
    """Sonst entstuenden Kosten fuer eine Pruefung, die niemand bekommt."""
    from app.database import SessionLocal
    from app.models import User

    headers = register(client, "pleite@test.ch")
    tid = _thema_mit_zielen(client, headers)
    aufrufe = []
    _mit_ki(monkeypatch, aufrufe=aufrufe)
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == "pleite@test.ch").one()
        u.free_used_tokens = 999
        u.free_month = quota.current_month()
        u.token_balance = 0
        db.commit()

    r = client.post(f"/api/topics/{tid}/pruefung", headers=headers)
    assert r.status_code == 402
    assert aufrufe == [], "bei leerem Guthaben darf kein Modell laufen"


# ---- Abgeben und korrigieren ----

def _erzeuge(client, headers, monkeypatch):
    tid = _thema_mit_zielen(client, headers)
    _mit_ki(monkeypatch)
    return tid, client.post(f"/api/topics/{tid}/pruefung", headers=headers).json()


def test_korrektur_laeuft_ohne_modellaufruf(client, monkeypatch):
    """Der Kern der Idee: korrigiert wird mit SymPy, nicht mit der KI."""
    headers = register(client, "korrektur@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    aufrufe = []
    _mit_ki(monkeypatch, aufrufe=aufrufe)  # ab jetzt zaehlen wir Modellaufrufe

    items = pruefung["items"]
    antworten = [
        {"id": items[0]["id"], "answer": "x = 5"},    # richtig
        {"id": items[1]["id"], "answer": "x = 5"},    # richtig (x + 7 = 12)
        {"id": items[2]["id"], "answer": "42"},       # richtig
        {"id": items[3]["id"], "answer": "x = 99"},   # falsch
        {"id": items[4]["id"], "answer": "irgendwas"},
        {"id": items[5]["id"], "answer": "gezeichnet"},
    ]
    r = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers,
                    json={"antworten": antworten})
    assert r.status_code == 200, r.text
    ergebnis = r.json()
    assert ergebnis["status"] == "bewertet"
    assert aufrufe == [], "die Korrektur darf KEIN Modell kosten"

    nach_pos = {i["position"]: i for i in ergebnis["items"]}
    assert nach_pos[1]["verdict"] == "correct" and nach_pos[1]["judged_by"] == "sympy"
    assert nach_pos[3]["verdict"] == "correct"          # 24 + 18 = 42
    assert nach_pos[4]["verdict"] == "incorrect"        # 2x = 10 -> x = 5, nicht 99
    # ohne Pruefausdruck bleibt es unbewertet
    assert nach_pos[5]["verdict"] == "unknown" and nach_pos[5]["judged_by"] == ""
    assert nach_pos[6]["verdict"] == "unknown"


def test_note_landet_im_verlauf(client, monkeypatch):
    headers = register(client, "note@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    # alles falsch ausser den nicht bewertbaren
    antworten = [{"id": i["id"], "answer": "x = 999"} for i in pruefung["items"]]
    ergebnis = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers,
                           json={"antworten": antworten}).json()

    assert 1.0 <= ergebnis["grade_value"] <= 6.0
    noten = client.get(f"/api/grades/verlauf?topic_id={tid}", headers=headers).json()["noten"]
    assert len(noten) == 1
    assert noten[0]["source"] == "probe"
    assert noten[0]["exam_id"] == pruefung["id"]
    assert noten[0]["value"] == ergebnis["grade_value"]


def test_auswertung_zeigt_welche_ziele_sitzen(client, monkeypatch):
    headers = register(client, "ziele@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    items = {i["position"]: i for i in pruefung["items"]}
    antworten = [
        {"id": items[1]["id"], "answer": "x = 5"},     # Gleichungen: richtig
        {"id": items[2]["id"], "answer": "x = 5"},     # Gleichungen: richtig
        {"id": items[3]["id"], "answer": "42"},        # Kopfrechnen: richtig
        {"id": items[4]["id"], "answer": "x = 99"},    # Gleichungen: FALSCH
        {"id": items[5]["id"], "answer": "-"},
        {"id": items[6]["id"], "answer": "-"},
    ]
    e = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers,
                    json={"antworten": antworten}).json()
    # Trefferquote je Ziel – «2 von 3» sagt mehr als ein blosses «noch üben»
    nach_name = {z["name"]: z for z in e["ziele"]}
    assert nach_name["Kopfrechnen"] == {"name": "Kopfrechnen", "richtig": 1, "total": 1}
    assert nach_name["Gleichungen lösen"]["richtig"] == 2
    assert nach_name["Gleichungen lösen"]["total"] == 3


def test_zweimal_abgeben_geht_nicht(client, monkeypatch):
    headers = register(client, "doppelt@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    leer = {"antworten": []}
    assert client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers,
                       json=leer).status_code == 200
    r = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers, json=leer)
    assert r.status_code == 409
    # und es entsteht keine zweite Note
    assert len(client.get("/api/grades/verlauf", headers=headers).json()["noten"]) == 1


def test_pruefung_faesst_die_hilfe_leiter_nicht_an(client, monkeypatch):
    """Waehrend einer Pruefung gibt es keine Hinweise – also darf sich auch am
    Uebungs-Fortschritt des Themas nichts aendern."""
    from app.database import SessionLocal
    from app.models import Attempt

    headers = register(client, "leiter@test.ch")
    tid = _thema_mit_zielen(client, headers)
    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "3x = 15", "topic_id": tid}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
    with SessionLocal() as db:
        a = db.get(Attempt, aid)
        vorher = (a.hint_level, a.own_attempts, a.solved)

    _mit_ki(monkeypatch)
    p = client.post(f"/api/topics/{tid}/pruefung", headers=headers).json()
    client.post(f"/api/exams/{p['id']}/abgeben", headers=headers,
                json={"antworten": [{"id": i["id"], "answer": "x = 5"} for i in p["items"]]})

    with SessionLocal() as db:
        a = db.get(Attempt, aid)
        assert (a.hint_level, a.own_attempts, a.solved) == vorher


def test_fehler_als_uebungsaufgabe_uebernehmen(client, monkeypatch):
    """Der Kreis schliesst sich: was nicht sass, wird zur Uebungsaufgabe."""
    headers = register(client, "uebernehmen@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    item = pruefung["items"][0]

    r = client.post(f"/api/exams/{pruefung['id']}/items/{item['id']}/uebernehmen",
                    headers=headers)
    assert r.status_code == 201
    aufgaben = client.get(f"/api/topics/{tid}/exercises", headers=headers).json()
    assert any(a["text"] == item["question"] for a in aufgaben)


def test_fremde_pruefung_unerreichbar(client, monkeypatch):
    a = register(client, "eins@test.ch")
    b = register(client, "zwei@test.ch")
    _tid, pruefung = _erzeuge(client, a, monkeypatch)
    assert client.get(f"/api/exams/{pruefung['id']}", headers=b).status_code == 404
    assert client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=b,
                       json={"antworten": []}).status_code == 404


def test_note_aus_punkten():
    """0 % -> 1.0, 100 % -> 6.0, dazwischen linear."""
    assert exam_service.note_aus_punkten(0, 8) == 1.0
    assert exam_service.note_aus_punkten(8, 8) == 6.0
    assert exam_service.note_aus_punkten(4, 8) == 3.5
    assert exam_service.note_aus_punkten(0, 0) == 1.0   # kein Sturz bei leerer Prüfung


def test_leer_abgegebene_pruefung_gibt_keine_sechs(client, monkeypatch):
    """Ohne diese Regel bekaeme eine komplett leer abgegebene Pruefung eine 6.0:
    eine leere Antwort ist fuer SymPy schlicht «nicht erkennbar», und
    «nicht erkennbar» zaehlte zugunsten des Kindes."""
    headers = register(client, "leerabgabe@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)

    e = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers,
                    json={"antworten": []}).json()
    # Gar nichts bearbeitet: auch die nicht pruefbaren Aufgaben zaehlen dann
    # NICHT zugunsten des Kindes – «nicht bewertbar» gilt nur fuer eine
    # Aufgabe, die es tatsaechlich bearbeitet hat.
    assert [i["verdict"] for i in e["items"]] == ["leer"] * 6
    assert e["grade_value"] == 1.0


def test_nur_ein_teil_beantwortet(client, monkeypatch):
    """Was nicht beantwortet wurde, zaehlt als falsch – was richtig ist, zaehlt."""
    headers = register(client, "teilweise@test.ch")
    tid, pruefung = _erzeuge(client, headers, monkeypatch)
    items = {i["position"]: i for i in pruefung["items"]}
    e = client.post(f"/api/exams/{pruefung['id']}/abgeben", headers=headers, json={
        "antworten": [{"id": items[1]["id"], "answer": "x = 5"}]}).json()
    nach_pos = {i["position"]: i for i in e["items"]}
    assert nach_pos[1]["verdict"] == "correct"
    assert nach_pos[2]["verdict"] == "leer"


# ---- Warum die Pruefung live nie zustande kam ----

def test_vordenken_wird_beim_starken_modell_abgeschaltet(client, monkeypatch):
    """DER Fehler, der die Pruefung live lahmgelegt hat.

    Sonnet 5 denkt standardmaessig vor, wenn der Parameter FEHLT (Sonnet 4.6
    tat das nicht), und die Denk-Tokens zaehlen gegen max_tokens. Im Chat war
    das schon behoben – hier hatte ich es vergessen, und der Aufruf lief so
    lange, dass die Plattform die Funktion abschoss: null Pruefungen, null
    Nutzung, null Alarm. Haiku kennt den Schalter NICHT und wuerde einen
    Fehler werfen, deshalb darf er dort nicht mitgehen.
    """
    calls = []
    headers = register(client, "denken@test.ch")
    tid = _thema_mit_zielen(client, headers)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(exam_service, "anthropic", _fake_anthropic(calls=calls))

    assert client.post(f"/api/topics/{tid}/pruefung", headers=headers).status_code == 201
    assert len(calls) == 1
    assert calls[0]["model"] == settings.anthropic_model_smart
    # Als extra_body, nicht als Schluesselwort: das SDK 0.42 kennt «thinking»
    # nicht und warf einen TypeError, bevor die Anfrage die API erreichte.
    assert "thinking" not in calls[0]
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_kein_vordenk_schalter_fuer_das_standardmodell(client, monkeypatch):
    """Haiku kennt den Schalter nicht – er darf dort nicht mitgeschickt werden."""
    calls = []
    headers = register(client, "denken2@test.ch")
    tid = _thema_mit_zielen(client, headers)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("overloaded")   # erzwingt den Wechsel auf Haiku
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=MODELL_ANTWORT)],
                usage=types.SimpleNamespace(input_tokens=1500, output_tokens=1300,
                                            cache_read_input_tokens=0,
                                            cache_creation_input_tokens=0))

    class _Client:
        def __init__(self, api_key, **kwargs):
            self.messages = _Messages()

    monkeypatch.setattr(exam_service, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    assert client.post(f"/api/topics/{tid}/pruefung", headers=headers).status_code == 201
    assert calls[1]["model"] == settings.anthropic_model_default
    assert "thinking" not in calls[1] and "extra_body" not in calls[1]


def test_zeitbudget_passt_unter_den_deckel_der_plattform():
    """Vercel bricht nach 60 s ab. Es muessen ZWEI Modellversuche hineinpassen.

    Vorher: 20 s Zeitlimit MIT einer SDK-Wiederholung waeren 2x20 pro Modell,
    also 80 s fuer beide – die Funktion wird abgeschossen, bevor irgendetwas
    gespeichert oder ein Alarm geschrieben ist.
    """
    assert exam_service.CLIENT_TIMEOUT * 2 + 10 < 60
    assert exam_service.AUSWEICH_DEADLINE + exam_service.CLIENT_TIMEOUT < 60


def test_keine_sdk_wiederholung(client, monkeypatch):
    """max_retries muss 0 sein: die Wiederholung leistet der Modellwechsel.
    Zwei SDK-Versuche ZUSAETZLICH sprengen das Zeitbudget."""
    gesehen = {}
    headers = register(client, "retry@test.ch")
    tid = _thema_mit_zielen(client, headers)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    class _Messages:
        def create(self, **kwargs):
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=MODELL_ANTWORT)],
                usage=types.SimpleNamespace(input_tokens=1500, output_tokens=1300,
                                            cache_read_input_tokens=0,
                                            cache_creation_input_tokens=0))

    class _Client:
        def __init__(self, api_key, **kwargs):
            gesehen.update(kwargs)
            self.messages = _Messages()

    monkeypatch.setattr(exam_service, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    client.post(f"/api/topics/{tid}/pruefung", headers=headers)
    assert gesehen["max_retries"] == 0
    assert gesehen["timeout"] == exam_service.CLIENT_TIMEOUT
