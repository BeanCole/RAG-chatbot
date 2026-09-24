import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.rag_service import analyze_query, generate_answer_stream

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", summary="Chat với Trợ lý ảo E-commerce")
async def chat_with_bot(request: ChatRequest):
    """
    Nhận câu hỏi và trả về câu trả lời dạng Server-Sent Events.

    Bộ lọc danh mục / giá do client gửi sẽ được ưu tiên; nếu thiếu, hệ thống
    tự phân tích câu hỏi bằng LLM để suy ra.
    """
    history = [m.model_dump() for m in request.history]
    inferred = analyze_query(request.query)

    category = request.category if request.category is not None else inferred.category
    max_price = (
        request.max_price if request.max_price is not None else inferred.max_price
    )
    logger.info("chat filters: category=%s max_price=%s", category, max_price)

    return StreamingResponse(
        generate_answer_stream(
            query=request.query,
            category=category,
            max_price=max_price,
            history=history,
        ),
        media_type="text/event-stream",
    )
