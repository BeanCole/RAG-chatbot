"""Split raw product documents into overlapping chunks for embedding."""

import json
import logging
import os

from app.config import settings
from app.services.chunking import split_document

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def transform_jsonl_to_chunks(input_file: str, output_file: str) -> int:
    # Keyed by chunk_id so re-runs are deterministic and ordered.
    chunks: dict[str, dict] = {}
    with open(input_file, encoding="utf-8") as infile:
        for line in infile:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            records = split_document(
                doc.get("content", ""),
                doc.get("doc_id", "unknown_id"),
                doc.get("metadata", {}),
            )
            for record in records:
                chunks[record["chunk_id"]] = record

    with open(output_file, "w", encoding="utf-8") as outfile:
        for record in chunks.values():
            outfile.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Wrote %d chunks to %s", len(chunks), output_file)
    return len(chunks)


if __name__ == "__main__":
    transform_jsonl_to_chunks(
        os.path.join(settings.data_dir, "products_data_raws.jsonl"),
        os.path.join(settings.data_dir, "products_data_chunks.jsonl"),
    )
