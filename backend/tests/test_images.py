"""Aufgaben-Bilder: dauerhafte Ablage in der DB statt fluechtigem /tmp."""
from .test_library import register_pw, tiny_png


def test_ocr_upload_stores_image_in_db(client):
    headers = register_pw(client, "mia@test.ch")

    r = client.post(
        "/api/exercises/ocr",
        headers=headers,
        files={"file": ("stift-eingabe.png", tiny_png(), "image/png")},
    )
    assert r.status_code == 200, r.text
    path = r.json()["image_path"]
    # neue Bilder haengen NICHT mehr am fluechtigen /uploads-Verzeichnis
    assert path.startswith("/api/exercises/images/")

    # Abruf ohne Auth (img-src schickt keinen Bearer) – Token ist die Capability
    f = client.get(path)
    assert f.status_code == 200
    assert f.headers["content-type"] == "image/png"
    assert f.content == tiny_png()  # kleines PNG bleibt verlustfrei erhalten

    # unbekannter Token -> 404
    assert client.get("/api/exercises/images/gibtsnicht").status_code == 404


def test_history_builder_embeds_task_image():
    """Mit Bild wird die erste User-Nachricht zu [image, text]-Bloecken."""
    from app.services.tutor import _history_to_messages

    history = [
        {"role": "tutor", "text": "Los geht's! Deine Aufgabe: ..."},
        {"role": "student", "text": "keine ahnung"},
    ]
    plain = _history_to_messages(history)
    assert isinstance(plain[0]["content"], str)  # ohne Bild: unveraendert

    msgs = _history_to_messages(history, image=(b"PNGBYTES", "image/png"))
    first = msgs[0]
    assert first["role"] == "user"
    assert first["content"][0]["type"] == "image"
    assert first["content"][0]["source"]["media_type"] == "image/png"
    assert first["content"][1]["type"] == "text"


def test_chat_works_with_and_without_task_image(client):
    """Aufgabe mit Bild-Referenz: Chat laeuft (Mock-Pfad); kaputter Pfad schadet nicht."""
    headers = register_pw(client, "mia@test.ch")

    up = client.post("/api/exercises/ocr", headers=headers,
                     files={"file": ("skizze.png", tiny_png(), "image/png")})
    image_path = up.json()["image_path"]

    for path in (image_path, "/api/exercises/images/gibtsnicht", "/uploads/alt.png"):
        ex = client.post("/api/exercises", headers=headers,
                         json={"text": "Wie gross ist die Fläche?", "image_path": path}).json()
        aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=headers).json()["attempt"]["id"]
        with client.stream("POST", f"/api/attempts/{aid}/chat", headers=headers,
                           json={"text": "ich weiss nicht"}) as r:
            assert r.status_code == 200
            assert "".join(r.iter_text())


def test_large_photo_is_recompressed(client):
    """Grosse Fotos werden verkleinert (JPEG) – bleibt unter dem Antwort-Limit."""
    import io

    from PIL import Image

    headers = register_pw(client, "mia@test.ch")
    buf = io.BytesIO()
    Image.new("RGB", (2400, 1800), "white").save(buf, format="JPEG", quality=95)
    r = client.post(
        "/api/exercises/ocr",
        headers=headers,
        files={"file": ("foto.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    f = client.get(r.json()["image_path"])
    assert f.status_code == 200
    assert f.headers["content-type"] == "image/jpeg"
    img = Image.open(io.BytesIO(f.content))
    assert max(img.size) <= 1600  # laengste Kante verkleinert


def test_ocr_leer_erlaubt_start_mit_bild(client):
    """Erkennt die KI nichts, bleibt das Bild gespeichert und die Aufgabe
    kann mit Platzhalter-Text (Frontend) trotzdem starten."""
    headers = register_pw(client, "leer@test.ch")
    r = client.post("/api/exercises/ocr", headers=headers,
                    files={"file": ("figur.png", tiny_png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["image_path"]  # Bild da, auch ohne erkannten Text

    ex = client.post("/api/exercises", headers=headers,
                     json={"text": "(Aufgabe auf dem Foto)", "image_path": body["image_path"]})
    assert ex.status_code == 201
    assert ex.json()["image_path"] == body["image_path"]


def test_ocr_upload_accepts_heic(client):
    """iPhone-Fotos (HEIC) werden akzeptiert und als JPEG gespeichert."""
    import io

    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="HEIF")

    headers = register_pw(client, "iphone@test.ch")
    r = client.post("/api/exercises/ocr", headers=headers,
                    files={"file": ("foto.heic", buf.getvalue(), "image/heic")})
    assert r.status_code == 200, r.text
    path = r.json()["image_path"]
    f = client.get(path)
    assert f.status_code == 200
    assert f.headers["content-type"] == "image/jpeg"  # konvertiert gespeichert
