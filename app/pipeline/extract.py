"""Extract active products from MySQL into a JSONL file for the transform step."""

import json
import logging
import os

from sqlalchemy import text

from app.clients import get_engine
from app.config import settings
from app.services.chunking import product_content

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def extract_products_data_to_jsonl(output_file: str) -> int:
    logger.info("Extracting products from MySQL...")
    count = 0
    with get_engine().connect() as connection:
        result = connection.execute(
            text(
                "SELECT product_id, name, description, price, category "
                "FROM products WHERE status = 'active'"
            )
        )
        with open(output_file, "w", encoding="utf-8") as f:
            for row in result:
                doc = {
                    "doc_id": f"prod_{row.product_id}",
                    "content": product_content(row.name, row.description),
                    "metadata": {
                        "category": row.category or "uncategorized",
                        "price": float(row.price) if row.price else 0.0,
                        "type": "product_info",
                    },
                }
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1
    logger.info("Extracted %d products to %s", count, output_file)
    return count


if __name__ == "__main__":
    output_file = os.path.join(settings.data_dir, "products_data_raws.jsonl")
    extract_products_data_to_jsonl(output_file)

    logger.info("Preview (first 2 rows):")
    with open(output_file, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 2:
                break
            print(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
