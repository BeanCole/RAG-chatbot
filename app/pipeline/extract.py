import json
import os
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
_logger = logging.getLogger(__name__)

DATA_DIR = "/app/data"
# DB_URL = os.getenv("DATABASE_URL")
DB_URL = "mysql+pymysql://root:root@mysql:3306/ecommerce_db?charset=utf8mb4"
engine = create_engine(DB_URL)
_logger = logging.getLogger(__name__)

def extract_products_data_to_jsonl(output_file: str):
    _logger.info("Extracting products data from MySQL database...")
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT product_id, name, description, price, category
                FROM products
                WHERE status = 'active'
            """)
            result = connection.execute(query)
            with open(output_file, "w", encoding="utf-8") as f:
                for row in result:
                    safe_desc = row.description if row.description else "Không có mô tả chi tiết"
                    safe_category = row.category if row.category else "uncategorized"
                    safe_price = float(row.price) if row.price else 0.0

                    context_text = f"Tên sản phẩm: {row.name}\nMô tả: {safe_desc}"

                    doc = {
                        "doc_id": f"prod_{row.product_id}",
                        "content": context_text,
                        "metadata": {
                            "category": safe_category,
                            "price": safe_price,
                            "type": "product_info"
                        }
                    }
                    f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                
        _logger.info(f"Products data extracted to {output_file} successfully.")
    except Exception as e:
        _logger.error(f"Error extracting products data: {e}")
        raise

if __name__ == "__main__":
    output_file = "/app/data/products_data_raws.jsonl"
    _logger.info(f"Starting data extraction to {output_file}...")
    try:
        extract_products_data_to_jsonl(output_file)

        print(f"KIỂM TRA KẾT QUẢ (In thử 2 dòng đầu tiên):")
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i < 2: # Chỉ in 2 sản phẩm đầu
                        # Format lại JSON cho dễ nhìn trên terminal
                        parsed_json = json.loads(line)
                        print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
        else:
            print(f"File {output_file} không tồn tại. Vui lòng kiểm tra lại.")
    except Exception as e:
        print(f"Đã xảy ra lỗi trong quá trình trích xuất dữ liệu: {e}")
