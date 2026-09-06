import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rag_service import QueryFilters


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_streams_sse(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.chat_router.analyze_query", lambda *a, **k: QueryFilters()
    )
    monkeypatch.setattr(
        "app.api.chat_router.generate_answer_stream",
        lambda **kwargs: iter(['data: "hi"\n\n', "data: [DONE]\n\n"]),
    )
    resp = client.post("/api/chat", json={"query": "balo"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in resp.text


def test_client_filters_override_inferred(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.chat_router.analyze_query",
        lambda *a, **k: QueryFilters(category="dien_tu", max_price=999),
    )
    captured = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return iter(["data: [DONE]\n\n"])

    monkeypatch.setattr("app.api.chat_router.generate_answer_stream", fake_stream)
    client.post(
        "/api/chat",
        json={"query": "balo", "category": "thoi_trang", "max_price": 500000},
    )
    assert captured["category"] == "thoi_trang"
    assert captured["max_price"] == 500000


def test_chat_requires_query(client):
    assert client.post("/api/chat", json={}).status_code == 422
