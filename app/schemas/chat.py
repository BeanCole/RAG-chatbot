from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi của khách hàng")
    category: Optional[str] = Field(
        None,
        description="Lọc theo danh mục (VD: dien_tu, thoi_trang). Ghi đè phân tích tự động.",
    )
    max_price: Optional[float] = Field(
        None, description="Mức giá tối đa (VD: 1000000). Ghi đè phân tích tự động."
    )
    history: list[ChatMessage] = Field(
        default_factory=list, description="Lịch sử hội thoại các lượt trước"
    )
