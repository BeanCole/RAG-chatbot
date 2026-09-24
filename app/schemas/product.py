from typing import Optional

from pydantic import BaseModel, Field

from app.categories import Category


class ProductCreate(BaseModel):
    name: str = Field(..., description="Tên sản phẩm")
    description: Optional[str] = Field(None, description="Mô tả sản phẩm")
    category: Optional[Category] = Field(
        None,
        description="Danh mục: dien_tu hoặc thoi_trang (phải khớp danh mục chatbot hiểu)",
    )
    price: float = Field(..., ge=0, description="Giá bán (VNĐ)")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Category] = None
    price: Optional[float] = Field(None, ge=0)


class ProductResponse(BaseModel):
    product_id: int
    name: str
    description: Optional[str]
    # str (not Category) on the way out: rows created before this constraint
    # existed may still carry an old free-text category — don't fail reading them.
    category: Optional[str]
    price: float
    status: str
    indexed_points: Optional[int] = None
