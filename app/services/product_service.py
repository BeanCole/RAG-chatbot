"""CRUD for products in MySQL, kept in sync with the Qdrant index."""

import logging

from sqlalchemy import text

from app.clients import get_engine
from app.services.indexing_service import delete_product_points, index_product

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    return {
        "product_id": row.product_id,
        "name": row.name,
        "description": row.description,
        "category": row.category,
        "price": float(row.price),
        "status": row.status,
    }


def get_product(product_id: int) -> dict | None:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT product_id, name, description, category, price, status "
                "FROM products WHERE product_id = :pid"
            ),
            {"pid": product_id},
        ).first()
    return _row_to_dict(row) if row else None


def create_product(data: dict) -> dict:
    with get_engine().begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO products (name, description, category, price) "
                "VALUES (:name, :description, :category, :price)"
            ),
            data,
        )
        product_id = result.lastrowid
    product = get_product(product_id)
    assert product is not None
    product["indexed_points"] = index_product(
        product_id,
        product["name"],
        product["description"],
        product["category"],
        product["price"],
    )
    return product


def update_product(product_id: int, changes: dict) -> dict | None:
    if not get_product(product_id):
        return None
    if changes:
        assignments = ", ".join(f"{key} = :{key}" for key in changes)
        with get_engine().begin() as conn:
            conn.execute(
                text(f"UPDATE products SET {assignments} WHERE product_id = :pid"),
                {**changes, "pid": product_id},
            )
    product = get_product(product_id)
    assert product is not None
    product["indexed_points"] = index_product(
        product_id,
        product["name"],
        product["description"],
        product["category"],
        product["price"],
    )
    return product


def soft_delete_product(product_id: int) -> bool:
    if not get_product(product_id):
        return False
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE products SET status = 'inactive' WHERE product_id = :pid"),
            {"pid": product_id},
        )
    delete_product_points(product_id)
    return True
