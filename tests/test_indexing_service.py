from app.services import indexing_service
from app.services.indexing_service import (
    _point_id,
    doc_id_for,
    embed_texts,
    index_product,
    upsert_chunks,
)


def test_point_id_is_deterministic():
    assert _point_id("prod_1_chunk_0") == _point_id("prod_1_chunk_0")
    assert _point_id("prod_1_chunk_0") != _point_id("prod_1_chunk_1")


def test_embed_texts_batches_single_request(fake_openai):
    vectors = embed_texts(["a", "b", "c"])
    assert len(vectors) == 3
    assert len(fake_openai.embed_calls) == 1


def test_upsert_chunks_writes_points(fake_openai, fake_qdrant):
    chunks = [
        {
            "chunk_id": f"prod_1_chunk_{i}",
            "parent_doc_id": "prod_1",
            "content": f"c{i}",
            "metadata": {},
        }
        for i in range(3)
    ]
    written = upsert_chunks(chunks)
    assert written == 3
    assert len(fake_qdrant.upserted) == 3


def test_index_product_deletes_then_upserts(fake_openai, fake_qdrant):
    n = index_product("7", "Balo", "vải dù", "thoi_trang", 450000)
    assert n >= 1
    assert fake_qdrant.deleted, "old points should be deleted before re-index"
    assert doc_id_for("7") == "prod_7"


def test_embed_texts_retries_on_rate_limit(fake_openai, monkeypatch):
    import httpx
    from openai import RateLimitError

    calls = {"n": 0}
    real = fake_openai.embeddings.create

    def flaky(model, input):
        calls["n"] += 1
        if calls["n"] < 2:
            resp = httpx.Response(429, request=httpx.Request("POST", "http://test"))
            raise RateLimitError("slow down", response=resp, body=None)
        return real(model=model, input=input)

    monkeypatch.setattr(fake_openai.embeddings, "create", flaky)
    # tenacity waits use real time; patch sleep to keep the test fast
    monkeypatch.setattr(indexing_service.embed_texts.retry, "sleep", lambda _: None)
    vectors = embed_texts(["a"])
    assert len(vectors) == 1
    assert calls["n"] == 2
