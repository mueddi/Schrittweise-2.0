"""Test-Setup: eigene SQLite-DB, frisch pro Test.

DATABASE_URL muss VOR dem App-Import gesetzt sein (engine entsteht beim Import).
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_schrittweise.db"
os.environ["MAGIC_LINK_DEV_RETURN"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""  # Mock-Tutor erzwingen

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def register(client: TestClient, email: str, role: str = "student", name: str = "Test") -> dict:
    """Registriert ein Konto und liefert Auth-Header."""
    r = client.post(
        "/api/auth/request-link",
        json={"email": email, "register": True, "display_name": name, "role": role},
    )
    assert r.status_code == 200, r.text
    token = r.json()["dev_token"]
    v = client.post("/api/auth/verify", json={"token": token})
    assert v.status_code == 200, v.text
    return {"Authorization": f"Bearer {v.json()['access_token']}"}
