from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging

# Import hÃ m sinh cÃ¢u tráº£ lá»i tá»« táº§ng Service mÃ  ta vá»«a viáº¿t
from app.services.rag_service import generate_answer_stream, analyze_query
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)

# init router
router = APIRouter()

@router.post("/chat", summary="Chat vá»›i Trá»£ lÃ½ áº£o E-commerce")
async def chat_with_bot(request: ChatRequest):
    """
    Endpoint nháº­n cÃ¢u há»i vÃ  tráº£ vá» cÃ¢u tráº£ lá»i dáº¡ng Stream (SSE).
    Há»— trá»£ lá»c trÆ°á»›c theo danh má»¥c vÃ  giÃ¡ tiá»n Ä‘á»ƒ tÄƒng Ä‘á»™ chÃ­nh xÃ¡c.
    """
    try:
        filters = analyze_query(request.query)
        print(f"PhÃ¢n tÃ­ch cÃ¢u há»i, trÃ­ch xuáº¥t Ä‘Æ°á»£c bá»™ lá»c: {filters}")
        answer_generator = generate_answer_stream(
            query=request.query,
            category=filters.get("category"),
            max_price=filters.get("max_price")
        )
        return StreamingResponse(
            answer_generator,
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"âŒ Lá»—i táº¡i endpoint /chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Lá»—i há»‡ thá»‘ng ná»™i bá»™. Vui lÃ²ng thá»­ láº¡i sau.")
