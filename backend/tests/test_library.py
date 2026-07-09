"""Aufgaben-Bibliothek: Admin-Guards, Upload/Download, Filter, Suche."""
import io

from app.database import SessionLocal
from app.models import User
from app.routers import library as library_router


def make_admin(email: str) -> None:
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        u.is_admin = True
        db.commit()


def register_pw(client, email: str, password: str = "test-passwort-123") -> dict:
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def tiny_png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, format="PNG")
    return buf.getvalue()


def upload(client, headers, title="Brüche kürzen", desc="Übungen zum Kürzen von Brüchen",
           category="zahlen", grades="1. Oberstufe,2. Oberstufe", difficulty="leicht"):
    return client.post(
        "/api/library",
        headers=headers,
        data={"title": title, "description": desc, "category": category,
              "grade_levels": grades, "difficulty": difficulty},
        files={"file": ("blatt.png", tiny_png(), "image/png")},
    )


def test_admin_routes_forbidden_for_students(client):
    headers = register_pw(client, "schueler@test.ch")
    assert upload(client, headers).status_code == 403
    assert client.delete("/api/library/1", headers=headers).status_code == 403
    assert client.patch("/api/library/1", headers=headers, json={"title": "x"}).status_code == 403
    # Lesen ohne Login -> 401
    assert client.get("/api/library").status_code == 401


def test_upload_list_filter_download_roundtrip(client):
    admin = register_pw(client, "admin@test.ch")
    make_admin("admin@test.ch")

    r = upload(client, admin)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["grade_levels"] == ["1. Oberstufe", "2. Oberstufe"]
    assert "content" not in doc

    upload(client, admin, title="Lineare Gleichungen", desc="Gleichungen lösen",
           category="algebra", grades="3. Oberstufe", difficulty="schwer")

    student = register_pw(client, "mia@test.ch")
    alle = client.get("/api/library", headers=student).json()
    assert len(alle) == 2

    nur_algebra = client.get("/api/library?category=algebra", headers=student).json()
    assert [d["title"] for d in nur_algebra] == ["Lineare Gleichungen"]

    nur_erste = client.get("/api/library?grade=1.%20Oberstufe", headers=student).json()
    assert [d["title"] for d in nur_erste] == ["Brüche kürzen"]

    nur_schwer = client.get("/api/library?difficulty=schwer", headers=student).json()
    assert [d["title"] for d in nur_schwer] == ["Lineare Gleichungen"]

    f = client.get(f"/api/library/{doc['id']}/file", headers=student)
    assert f.status_code == 200
    assert f.headers["content-type"] == "image/png"
    assert f.content == tiny_png()


def test_search_fallback_and_ai_ranking(client, monkeypatch):
    admin = register_pw(client, "admin@test.ch")
    make_admin("admin@test.ch")
    a = upload(client, admin, title="Brüche kürzen", desc="Brüche üben").json()
    b = upload(client, admin, title="Lineare Gleichungen", desc="Gleichungen mit x").json()

    student = register_pw(client, "mia@test.ch")

    # Ohne API-Key (Test-Env) -> Textsuche-Fallback
    hit = client.get("/api/library?q=gleichung", headers=student).json()
    assert [d["id"] for d in hit] == [b["id"]]

    # KI-Ranking bestimmt die Reihenfolge
    monkeypatch.setattr(library_router, "rank_documents", lambda q, docs: [b["id"], a["id"]])
    ranked = client.get("/api/library?q=irgendwas", headers=student).json()
    assert [d["id"] for d in ranked] == [b["id"], a["id"]]

    # KI sagt «nichts passt» ([]) -> leeres Ergebnis, kein Fallback
    monkeypatch.setattr(library_router, "rank_documents", lambda q, docs: [])
    assert client.get("/api/library?q=quantenphysik", headers=student).json() == []


def test_upload_validation(client):
    admin = register_pw(client, "admin@test.ch")
    make_admin("admin@test.ch")

    # Falsche Magic-Bytes: PNG-Bytes als PDF deklariert
    r = client.post(
        "/api/library", headers=admin,
        data={"title": "t", "description": "d", "category": "andere",
              "grade_levels": "1. Oberstufe", "difficulty": "mittel"},
        files={"file": ("x.pdf", tiny_png(), "application/pdf")},
    )
    assert r.status_code == 400

    # Zu gross (>4 MB)
    big = b"%PDF-" + b"0" * (4 * 1024 * 1024 + 100)
    r = client.post(
        "/api/library", headers=admin,
        data={"title": "t", "description": "d", "category": "andere",
              "grade_levels": "1. Oberstufe", "difficulty": "mittel"},
        files={"file": ("gross.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413

    # Ungültige Klassenstufe
    r = upload(client, admin, grades="5. Klasse")
    assert r.status_code == 400


def test_update_and_delete(client):
    admin = register_pw(client, "admin@test.ch")
    make_admin("admin@test.ch")
    doc = upload(client, admin).json()

    r = client.patch(f"/api/library/{doc['id']}", headers=admin,
                     json={"title": "Neuer Titel", "difficulty": "schwer"})
    assert r.status_code == 200
    assert r.json()["title"] == "Neuer Titel"
    assert r.json()["difficulty"] == "schwer"

    assert client.delete(f"/api/library/{doc['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/library/{doc['id']}/file", headers=admin).status_code == 404
