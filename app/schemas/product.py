from pydantic import BaseModel, Field

class ProductUpdatePayload(BaseModel):
    product_id: str = Field(..., description="ID gốc của sản phẩm")
    name: str
    description: str
    category: str
    price: float