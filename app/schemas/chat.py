from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi của khách hàng")
    category: Optional[str] = Field(None, description="Lọc theo danh mục (VD: dien_tu, thoi_trang, nha_cua, ...)")
    max_price: Optional[float] = Field(None, description="Mức giá tối đa (VD: 1000000)")