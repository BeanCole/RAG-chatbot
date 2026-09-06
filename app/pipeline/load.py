"""Embed product chunks and load them into Qdrant."""

import json
import logging
import os

from app.config import settings
from app.services.indexing_service import setup_collection, upsert_chunks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def load_chunks(input_file: str) -> int:
    with open(input_file, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    logger.info("Loaded %d chunks from %s", len(chunks), input_file)
    return upsert_chunks(chunks)


if __name__ == "__main__":
    setup_collection()
    total = load_chunks(os.path.join(settings.data_dir, "products_data_chunks.jsonl"))
    logger.info("Done. %d points in '%s'.", total, settings.collection_name)
