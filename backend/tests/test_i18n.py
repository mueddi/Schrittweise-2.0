"""Zweisprachigkeit (de/en) + Stufen-Logik (mittelstufe/oberstufe/gymnasium)."""
from .test_library import register_pw


def _mit_sprache(client, email, lang):
    headers = register_pw(client, email)
    r = client.patch("/api/auth/me", headers=headers, json={"language": lang})
    assert r.status_code == 200
    assert r.json()["language"] == lang
    return headers


def test_opener_und_mock_tutor_auf_englisch(client):
    headers = _mit_sprache(client, "en@test.ch", "en")

    ex = client.post("/api/exercises", headers=headers, json={"text": "3x + 5 = 20"}).json()
    state = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()
    opener = state["messages"][0]["text"]
    assert "Let's go" in opener
    assert "Los geht" not in opener

    aid = state["attempt"]["id"]
    with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                       json={"text": "no idea"}) as r:
        assert r.status_code == 200
        reply = "".join(r.iter_text())
    assert "No stress" in reply  # englischer Mock-Tutor


def test_fehlermeldungen_auf_englisch(client):
    headers = _mit_sprache(client, "en2@test.ch", "en")
    # 404 einer fremden Session in Nutzersprache
    r = client.get("/api/attempts/999999", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Session not found"

    # Login-Fehler vor dem Einloggen: Sprache kommt aus dem X-Lang-Header
    r = client.post("/api/auth/login", headers={"X-Lang": "en"},
                    json={"email": "gibtsnicht@test.ch", "password": "falschfalsch"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Email or password is incorrect."


def test_deutsch_bleibt_standard(client):
    headers = register_pw(client, "de@test.ch")
    ex = client.post("/api/exercises", headers=headers, json={"text": "3x + 5 = 20"}).json()
    opener = client.post(f"/api/exercises/{ex['id']}/attempts",
                         headers=headers).json()["messages"][0]["text"]
    assert "Los geht's" in opener


def test_regie_kennt_die_drei_stufen():
    from app.services.tutor import LadderStep, _regie
    from app.services.sympy_verifier import Verification

    v = Verification(status="unknown", detail="-", solution=None)
    step = LadderStep("question", 1, 0, False, False)

    gymi = _regie(step, v, "f(x) = x^2", None, "gymnasium")
    assert "Matura" in gymi
    mittel = _regie(step, v, "12 + 7", None, "mittelstufe")
    assert "Mittelstufe" in mittel and "einfache Sprache" in mittel
    ober = _regie(step, v, "3x + 5 = 20", None, "oberstufe")
    assert "Oberstufe" in ober
    # Legacy-Werte aus Alt-Konten funktionieren weiter
    legacy = _regie(step, v, "f(x) = x^2", None, "Gymnasium 1./2.")
    assert "Matura" in legacy


def test_system_prompt_erzwingt_englisch():
    from app.services.tutor import LadderStep, _build_system
    from app.services.sympy_verifier import Verification

    v = Verification(status="unknown", detail="-", solution=None)
    step = LadderStep("question", 1, 0, False, False)
    en = _build_system(step, v, "3x + 5 = 20", None, "oberstufe", "en")
    assert "Englisch" in en[1]["text"]
    de = _build_system(step, v, "3x + 5 = 20", None, "oberstufe", "de")
    assert "Englisch" not in de[1]["text"]
