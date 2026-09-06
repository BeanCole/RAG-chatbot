import pytest
from fastapi.testclient import TestClient

from app.api import health_router
from app.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ok(client, fake_qdrant, monkeypatch):
    fake_qdrant._collections.add(settings.collection_name)
    fake_qdrant.upserted = [1, 2, 3]

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            return None

    monkeypatch.setattr(
        health_router,
        "get_engine",
        lambda: type("E", (), {"connect": lambda self: FakeConn()})(),
    )
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mysql"] == "ok"
    assert body["qdrant"]["points"] == 3


def test_health_degraded_when_collection_missing(client, fake_qdrant, monkeypatch):
    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            return None

    monkeypatch.setattr(
        health_router,
        "get_engine",
        lambda: type("E", (), {"connect": lambda self: FakeConn()})(),
    )
    body = client.get("/health").json()
    assert body["status"] == "degraded"
