"""Shared fakes so tests never touch OpenAI, Qdrant or MySQL."""

import os
from types import SimpleNamespace

import pytest

# Force test values so a developer's real .env never leaks into the test process.
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["QDRANT_URL"] = "http://localhost:6333"


# --------------------------------------------------------------------------- #
# Fake OpenAI
# --------------------------------------------------------------------------- #
class FakeCompletions:
    def __init__(self, owner: "FakeOpenAI"):
        self._owner = owner

    def create(self, **kwargs):
        self._owner.chat_calls.append(kwargs)
        if kwargs.get("stream"):
            tokens = self._owner.stream_tokens
            return iter(
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=tok))]
                )
                for tok in tokens
            )
        content = self._owner.next_chat_response
        if callable(content):
            content = content(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeEmbeddings:
    def __init__(self, owner: "FakeOpenAI"):
        self._owner = owner

    def create(self, model, input):
        items = input if isinstance(input, list) else [input]
        self._owner.embed_calls.append(items)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1] * self._owner.dim) for _ in items]
        )


class FakeOpenAI:
    def __init__(self, dim: int = 1536):
        self.dim = dim
        self.chat = SimpleNamespace(completions=FakeCompletions(self))
        self.embeddings = FakeEmbeddings(self)
        self.chat_calls: list[dict] = []
        self.embed_calls: list[list[str]] = []
        self.stream_tokens: list[str] = ["Xin ", "chào"]
        self.next_chat_response = '{"category": null, "max_price": null}'


# --------------------------------------------------------------------------- #
# Fake Qdrant
# --------------------------------------------------------------------------- #
class FakeQdrant:
    def __init__(self):
        self.points: list = []
        self.upserted: list = []
        self.deleted: list = []
        self.query_calls: list[dict] = []
        self._collections: set[str] = set()

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return SimpleNamespace(points=list(self.points))

    def collection_exists(self, name):
        return name in self._collections

    def create_collection(self, collection_name, **kwargs):
        self._collections.add(collection_name)

    def get_collection(self, name):
        return SimpleNamespace(payload_schema={})

    def create_payload_index(self, **kwargs):
        pass

    def upsert(self, collection_name, points):
        self.upserted.extend(points)

    def delete(self, collection_name, points_selector):
        self.deleted.append(points_selector)

    def count(self, name, exact=True):
        return SimpleNamespace(count=len(self.upserted))


@pytest.fixture
def fake_openai(monkeypatch):
    fake = FakeOpenAI()
    for module in (
        "app.services.rag_service",
        "app.services.indexing_service",
    ):
        monkeypatch.setattr(f"{module}.get_openai", lambda: fake)
    return fake


@pytest.fixture
def fake_qdrant(monkeypatch):
    fake = FakeQdrant()
    for module in (
        "app.services.rag_service",
        "app.services.indexing_service",
        "app.api.health_router",
    ):
        monkeypatch.setattr(f"{module}.get_qdrant", lambda: fake)
    return fake
