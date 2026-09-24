"""Retrieval-augmented generation: analyze query -> retrieve -> (rerank) -> stream answer."""

import json
import logging
from collections.abc import Iterator
from typing import Optional

from pydantic import BaseModel, field_validator
from qdrant_client import models

from app.categories import Category
from app.clients import get_openai, get_qdrant
from app.config import settings

logger = logging.getLogger(__name__)

_ANALYZER_PROMPT = """Bạn là một chuyên gia phân tích dữ liệu sản phẩm. Hãy đọc câu hỏi và trả về ĐÚNG 1 ĐỊNH DẠNG JSON.
1. "category": "dien_tu" (điện thoại, tai nghe,...), "thoi_trang" (quần áo, balo,...), hoặc null nếu không rõ.
2. "max_price": CHÚ Ý - Phải dịch các từ chỉ tiền tệ sang số nguyên VNĐ:
 - Ví dụ: "10 triệu", "10 củ" -> 10000000
 - Ví dụ: "500k", "500 cành" -> 500000
 - Ví dụ: "dưới 2 triệu" -> 2000000
 - Nếu câu hỏi không nhắc đến hạn giá tối đa -> null

 Trả về duy nhất JSON, không thêm bất kỳ text nào khác.
"""

_SYSTEM_PROMPT = """Bạn là trợ lý ảo AI xuất sắc của hệ thống E-commerce.
QUY TẮC BẮT BUỘC:
1. Thông tin trong [NGỮ CẢNH SẢN PHẨM] là các sản phẩm ĐÃ ĐƯỢC HỆ THỐNG LỌC CHUẨN XÁC theo mức giá và danh mục khách yêu cầu.
2. Hãy TỰ TIN giới thiệu các sản phẩm này. TUYỆT ĐỐI KHÔNG được nói là "không có sản phẩm nào phù hợp" nếu trong ngữ cảnh có chứa sản phẩm.
3. KHÔNG tự ý so sánh toán học (lớn hơn, nhỏ hơn). Chỉ trình bày lại tên, mô tả và giá tiền của sản phẩm. Nếu có nhiều sản phẩm trong ngữ cảnh, hãy trình bày một cách thân thiện.
4. Nếu [NGỮ CẢNH SẢN PHẨM] hoàn toàn trống, lúc đó mới lịch sự xin lỗi khách hàng.

[NGỮ CẢNH SẢN PHẨM]:
{context_data}
"""

_EMPTY_ANSWER = (
    "Xin lỗi, hiện tại chúng tôi không tìm thấy sản phẩm phù hợp với yêu cầu của bạn."
)
_ERROR_ANSWER = "Hệ thống AI đang quá tải, vui lòng thử lại sau giây lát."


class RetrievalError(RuntimeError):
    """Raised when the retrieval layer fails (Qdrant / embeddings unavailable)."""


class QueryFilters(BaseModel):
    category: Optional[Category] = None
    max_price: Optional[float] = None

    @field_validator("max_price", mode="before")
    @classmethod
    def _coerce_price(cls, value: object) -> object:
        if value in ("", None):
            return None
        try:
            price = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return price if price > 0 else None


Message = dict[str, str]


def _history_messages(history: Optional[list[Message]]) -> list[Message]:
    if not history:
        return []
    trimmed = history[-settings.history_max_turns :]
    return [
        {"role": m["role"], "content": m["content"]}
        for m in trimmed
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


def analyze_query(query: str) -> QueryFilters:
    """Use the chat model to extract structured filters from a natural-language query.

    Deliberately ignores conversation history: an earlier turn's category/price
    would otherwise "leak" into an unrelated later question (e.g. asking about
    electronics, then "find anything under 1 million" incorrectly inheriting
    category=dien_tu and matching nothing). History is still used for the
    final answer in generate_answer_stream, where leaking context is what you
    want (resolving "that one") rather than a bug.
    """
    try:
        response = get_openai().chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": _ANALYZER_PROMPT},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = json.loads(response.choices[0].message.content or "{}")
        return QueryFilters.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - fall back to no filters on any failure
        logger.warning("analyze_query failed, using empty filters: %s", exc)
        return QueryFilters()


def _build_filter(
    category: Optional[str], max_price: Optional[float]
) -> Optional[models.Filter]:
    must: list[models.FieldCondition] = []
    if category:
        must.append(
            models.FieldCondition(
                key="metadata.category", match=models.MatchValue(value=category)
            )
        )
    if max_price:
        must.append(
            models.FieldCondition(
                key="metadata.price", range=models.Range(lte=max_price)
            )
        )
    return models.Filter(must=must) if must else None


def _rerank(query: str, points: list, top_k: int) -> list:
    """Ask the chat model to pick the most relevant candidates."""
    if len(points) <= top_k:
        return points
    catalog = "\n".join(
        f"{i}: {p.payload.get('content', '')}" for i, p in enumerate(points)
    )
    try:
        response = get_openai().chat.completions.create(
            model=settings.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Chọn các đoạn liên quan nhất tới câu hỏi. Trả về JSON "
                        '{"indices": [..]} theo thứ tự liên quan giảm dần.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Câu hỏi: {query}\n\nCác đoạn:\n{catalog}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        indices = json.loads(response.choices[0].message.content or "{}").get(
            "indices", []
        )
        ordered = [
            points[i] for i in indices if isinstance(i, int) and 0 <= i < len(points)
        ]
        if ordered:
            return ordered[:top_k]
    except Exception as exc:  # noqa: BLE001 - reranking is best-effort
        logger.warning("rerank failed, keeping vector order: %s", exc)
    return points[:top_k]


def retrieve_context(
    query: str, category: Optional[str] = None, max_price: Optional[float] = None
) -> str:
    """Vector search in Qdrant with metadata pre-filtering; returns formatted context."""
    try:
        embedding = (
            get_openai()
            .embeddings.create(model=settings.embedding_model, input=query)
            .data[0]
            .embedding
        )
        fetch_limit = settings.top_k * 3 if settings.rerank_enabled else settings.top_k
        result = get_qdrant().query_points(
            collection_name=settings.collection_name,
            query=embedding,
            query_filter=_build_filter(category, max_price),
            limit=fetch_limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Qdrant retrieval failed: %s", exc)
        raise RetrievalError(str(exc)) from exc

    points = result.points
    if not points:
        return ""
    if settings.rerank_enabled:
        points = _rerank(query, points, settings.top_k)

    blocks: list[str] = []
    for point in points:
        payload = point.payload or {}
        meta = payload.get("metadata", {})
        content = payload.get("content", "")
        chunk_type = payload.get("type") or meta.get("type", "product_info")
        if chunk_type == "policy":
            blocks.append(f"[CHÍNH SÁCH CỬA HÀNG]\n{content}")
        else:
            price = payload.get("price") or meta.get("price", 0)
            formatted = f"{price:,.0f}".replace(",", ".")
            blocks.append(f"[SẢN PHẨM]\n{content}\nGiá bán: {formatted} VNĐ")

    separator = "\n\n" + "=" * 30 + "\n\n"
    context = separator.join(blocks)
    logger.info("Context for LLM:\n%s", context)
    return context


def _sse_token(token: str) -> str:
    # JSON-encode so newlines / quotes in a token never break SSE framing.
    return f"data: {json.dumps(token, ensure_ascii=False)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def generate_answer_stream(
    query: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    history: Optional[list[Message]] = None,
) -> Iterator[str]:
    """Yield Server-Sent-Events frames: token frames then a final ``[DONE]`` sentinel."""
    try:
        context = retrieve_context(query, category, max_price)
    except RetrievalError:
        yield _sse_token(_ERROR_ANSWER)
        yield _sse_done()
        return

    if not context:
        yield _sse_token(_EMPTY_ANSWER)
        yield _sse_done()
        return

    try:
        response = get_openai().chat.completions.create(
            model=settings.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(context_data=context),
                },
                *_history_messages(history),
                {"role": "user", "content": query},
            ],
            stream=True,
            temperature=0.1,
        )
        for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield _sse_token(token)
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI streaming failed: %s", exc)
        yield _sse_token(_ERROR_ANSWER)
    finally:
        yield _sse_done()
