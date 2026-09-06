from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., description="Tên sản phẩm")
    description: Optional[str] = Field(None, description="Mô tả sản phẩm")
    category: Optional[str] = Field(
        None, description="Danh mục (VD: dien_tu, thoi_trang)"
    )
    price: float = Field(..., ge=0, description="Giá bán (VNĐ)")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)


class ProductResponse(BaseModel):
    product_id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    price: float
    status: str
    indexed_points: Optional[int] = None
