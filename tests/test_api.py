from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rejects_non_pdf() -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_rejects_fake_pdf() -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")},
    )
    assert response.status_code == 400
