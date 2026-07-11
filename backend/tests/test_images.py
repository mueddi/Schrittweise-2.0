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
