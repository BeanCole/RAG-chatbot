from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services import rag_service
from app.services.rag_service import (
    QueryFilters,
    RetrievalError,
    _build_filter,
    analyze_query,
    generate_answer_stream,
    retrieve_context,
)


def _point(
    content="Balo chống nước", price=450000, ptype="product_info", category="thoi_trang"
):
    return SimpleNamespace(
        score=0.9,
        payload={
            "content": content,
            "metadata": {"price": price, "type": ptype, "category": category},
        },
    )


# --- QueryFilters -----------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"category": "dien_tu", "max_price": "1000000"}, ("dien_tu", 1000000.0)),
        ({"category": None, "max_price": ""}, (None, None)),
        ({"category": "invalid"}, None),  # invalid enum -> ValidationError
        ({"max_price": 0}, (None, None)),
        ({"max_price": "abc"}, (None, None)),
    ],
)
def test_query_filters_validation(raw, expected):
    if expected is None:
        with pytest.raises(ValidationError):
            QueryFilters.model_validate(raw)
    else:
        f = QueryFilters.model_validate(raw)
        assert (f.category, f.max_price) == expected


# --- analyze_query --------------------------------------------------------
def test_analyze_query_parses_json(fake_openai):
    fake_openai.next_chat_response = '{"category": "thoi_trang", "max_price": 500000}'
    result = analyze_query("balo dưới 500k")
    assert result.category == "thoi_trang"
    assert result.max_price == 500000


def test_analyze_query_falls_back_on_bad_json(fake_openai):
    fake_openai.next_chat_response = "not json at all"
    result = analyze_query("balo")
    assert result == QueryFilters()


# --- _build_filter --------------------------------------------------------
def test_build_filter_combinations():
    assert _build_filter(None, None) is None
    both = _build_filter("dien_tu", 1_000_000)
    assert len(both.must) == 2


# --- retrieve_context ---------------------------------------------------
def test_retrieve_context_formats_product_and_policy(fake_openai, fake_qdrant):
    fake_qdrant.points = [
        _point(),
        _point(content="Đổi trả 7 ngày", ptype="policy"),
    ]
    ctx = retrieve_context("balo")
    assert "[SẢN PHẨM]" in ctx
    assert "450.000 VNĐ" in ctx
    assert "[CHÍNH SÁCH CỬA HÀNG]" in ctx
    assert "Đổi trả 7 ngày" in ctx


def test_retrieve_context_passes_filter_to_qdrant(fake_openai, fake_qdrant):
    fake_qdrant.points = [_point()]
    retrieve_context("balo", category="thoi_trang", max_price=500000)
    assert fake_qdrant.query_calls[0]["query_filter"] is not None


def test_retrieve_context_empty_when_no_points(fake_openai, fake_qdrant):
    fake_qdrant.points = []
    assert retrieve_context("balo") == ""


def test_retrieve_context_raises_on_backend_error(
    fake_openai, fake_qdrant, monkeypatch
):
    def boom(**kwargs):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(fake_qdrant, "query_points", boom)
    with pytest.raises(RetrievalError):
        retrieve_context("balo")


# --- generate_answer_stream ------------------------------------------------
def _collect(gen):
    return "".join(gen)


def test_stream_yields_sse_frames_and_done(fake_openai, fake_qdrant):
    fake_qdrant.points = [_point()]
    fake_openai.stream_tokens = ["Chào ", "bạn"]
    out = _collect(generate_answer_stream("balo"))
    assert 'data: "Chào "\n\n' in out
    assert out.endswith("data: [DONE]\n\n")


def test_stream_empty_context_returns_apology(fake_openai, fake_qdrant):
    fake_qdrant.points = []
    out = _collect(generate_answer_stream("balo"))
    assert "không tìm thấy sản phẩm" in out
    assert out.endswith("data: [DONE]\n\n")


def test_stream_handles_retrieval_error(fake_openai, fake_qdrant, monkeypatch):
    def boom(*args, **kwargs):
        raise RetrievalError("x")

    monkeypatch.setattr(rag_service, "retrieve_context", boom)
    out = _collect(generate_answer_stream("balo"))
    assert "quá tải" in out
    assert out.endswith("data: [DONE]\n\n")
