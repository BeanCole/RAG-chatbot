import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services import product_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate):
    """Thêm sản phẩm vào MySQL và index embedding vào Qdrant."""
    return product_service.create_product(payload.model_dump())


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int):
    product = product_service.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không tồn tại")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate):
    """Cập nhật sản phẩm và re-index (xoá point cũ, embed lại)."""
    changes = payload.model_dump(exclude_none=True)
    product = product_service.update_product(product_id, changes)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không tồn tại")
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int):
    """Soft delete (status='inactive') và xoá point khỏi Qdrant."""
    if not product_service.soft_delete_product(product_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sản phẩm không tồn tại")
