"""Embed product chunks and keep the Qdrant collection in sync.

Shared by the batch loader (`app.pipeline.load`) and the product admin API so
there is a single code path that turns a product into vector points.
"""

import logging
import uuid

from openai import APIError, RateLimitError
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.clients import get_openai, get_qdrant
from app.config import settings
from app.services.chunking import product_content, split_document

logger = logging.getLogger(__name__)

_PARENT_KEY = "parent_doc_id"
_REQUIRED_INDEXES = {
    "metadata.price": PayloadSchemaType.FLOAT,
    "metadata.category": PayloadSchemaType.KEYWORD,
}


def doc_id_for(product_id: str | int) -> str:
    return f"prod_{product_id}"


def setup_collection() -> None:
    """Create the collection and payload indexes if they do not exist yet."""
    client = get_qdrant()
    if not client.collection_exists(settings.collection_name):
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim, distance=Distance.COSINE
            ),
        )
        logger.info("Created collection '%s'", settings.collection_name)

    schema = client.get_collection(settings.collection_name).payload_schema
    for field_name, field_type in _REQUIRED_INDEXES.items():
        if field_name not in schema:
            client.create_payload_index(
                collection_name=settings.collection_name,
                field_name=field_name,
                field_schema=field_type,
            )
            logger.info("Created payload index '%s'", field_name)


@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts in a single request, retrying on transient errors."""
    response = get_openai().embeddings.create(
        model=settings.embedding_model, input=texts
    )
    return [item.embedding for item in response.data]


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def upsert_chunks(chunks: list[dict], batch_size: int = 100) -> int:
    """Embed and upsert chunk records. Returns the number of points written."""
    client = get_qdrant()
    written = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embed_texts([c["content"] for c in batch])
        points = [
            PointStruct(
                id=_point_id(c["chunk_id"]),
                vector=vector,
                payload={
                    "parent_doc_id": c.get("parent_doc_id", "unknown_parent_id"),
                    "content": c["content"],
                    "chunk_id": c["chunk_id"],
                    "metadata": c.get("metadata", {}),
                },
            )
            for c, vector in zip(batch, vectors, strict=True)
        ]
        client.upsert(collection_name=settings.collection_name, points=points)
        written += len(points)
        logger.info("Upserted %d points (%d total)", len(points), written)
    return written


def delete_product_points(product_id: str | int) -> None:
    get_qdrant().delete(
        collection_name=settings.collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key=_PARENT_KEY,
                    match=MatchValue(value=doc_id_for(product_id)),
                )
            ]
        ),
    )
    logger.info("Deleted Qdrant points for product %s", product_id)


def index_product(
    product_id: str | int,
    name: str,
    description: str | None,
    category: str | None,
    price: float | None,
) -> int:
    """(Re)index a single product: drop its old points, embed and upsert new ones."""
    doc_id = doc_id_for(product_id)
    metadata = {
        "category": category or "uncategorized",
        "price": float(price or 0.0),
        "type": "product_info",
    }
    chunks = split_document(product_content(name, description), doc_id, metadata)
    delete_product_points(product_id)
    return upsert_chunks(chunks)
