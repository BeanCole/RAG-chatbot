"""Shared text-chunking logic used by the batch pipeline and the live index API."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
)


def product_content(name: str, description: str | None) -> str:
    safe_desc = description or "Không có mô tả chi tiết"
    return f"Tên sản phẩm: {name}\nMô tả: {safe_desc}"


def split_document(content: str, doc_id: str, metadata: dict) -> list[dict]:
    """Split ``content`` into ordered chunk records.

    Mirrors the enrichment the pipeline applies: ``product_info`` chunks are
    prefixed with their parent id so the embedding keeps the association.
    """
    chunks = _splitter.split_text(content)
    records: list[dict] = []
    for i, chunk in enumerate(chunks):
        if metadata.get("type") == "product_info":
            enriched = f"[Thuộc sản phẩm id {doc_id}] {chunk}"
        else:
            enriched = chunk
        records.append(
            {
                "parent_doc_id": doc_id,
                "chunk_id": f"{doc_id}_chunk_{i}",
                "content": enriched,
                "metadata": metadata,
            }
        )
    return records
