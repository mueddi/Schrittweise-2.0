"""Launch-Sicherheit: Token-Hashing, Rate-Limit, Eingabe-Limits."""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import MagicLink

from .conftest import register


def test_magic_token_stored_hashed(client):
    r = client.post(
        "/api/auth/request-link",
        json={"email": "hash@test.ch", "register": True, "display_name": "H"},
    )
    raw = r.json()["dev_token"]
    with SessionLocal() as s:
        stored = s.scalars(select(MagicLink.token).where(MagicLink.email == "hash@test.ch")).all()
    assert raw not in stored              # Klartext liegt NICHT in der DB
    assert all(len(t) == 64 for t in stored)  # sha256-Hexdigest
    # Login mit dem Klartext-Token funktioniert trotzdem
    assert client.post("/api/auth/verify", json={"token": raw}).status_code == 200


def test_request_link_rate_limited(client):
    body = {"email": "spam@test.ch", "register": True, "display_name": "S"}
    for _ in range(5):
        assert client.post("/api/auth/request-link", json=body).status_code == 200
    r = client.post("/api/auth/request-link", json=body)
    assert r.status_code == 429


def test_chat_message_length_capped(client):
    h = register(client, "long@test.ch")
    ex = client.post("/api/exercises", headers=h,
                     json={"text": "3x+5=20", "math_expression": "3*x+5=20"}).json()
    aid = client.post(f"/api/exercises/{ex['id']}/attempts", headers=h).json()["attempt"]["id"]
    r = client.post(f"/api/attempts/{aid}/chat", headers=h, json={"text": "x" * 3000})
    assert r.status_code == 422


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
