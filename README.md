# RAG Chatbot E-commerce

Chatbot tìm kiếm sản phẩm bằng Retrieval-Augmented Generation (RAG), sử dụng FastAPI, OpenAI, Qdrant và MySQL.

## Tính năng

- Tìm kiếm sản phẩm bằng semantic search.
- Lọc theo danh mục và giá tối đa.
- Trả lời streaming qua API.
- Giao diện chat phục vụ trực tiếp bởi FastAPI.
- Pipeline Extract -> Transform -> Load dữ liệu sản phẩm.

## Kiến trúc

- **FastAPI**: API chat và frontend.
- **MySQL**: lưu sản phẩm.
- **Qdrant**: lưu vector embedding và tìm kiếm ngữ nghĩa.
- **OpenAI**: tạo embedding bằng `text-embedding-3-small`, phân tích câu hỏi và sinh câu trả lời bằng `gpt-4o-mini`.

```text
MySQL -> Extract -> JSONL -> Transform -> Chunks -> OpenAI Embeddings -> Qdrant
```

## Yêu cầu

- Docker Desktop đang chạy.
- OpenAI API key còn quota/billing.

Tạo file `.env` ở thư mục gốc:

```env
OPENAI_API_KEY=your_openai_api_key
```

Không commit hoặc chia sẻ file `.env`.

## Chạy ứng dụng

```powershell
docker compose up -d
docker compose ps
```

Các địa chỉ chính:

- Giao diện chat: http://localhost:8081/frontend/index.html
- Swagger API: http://localhost:8081/docs
- API root: http://localhost:8081/
- Qdrant: http://localhost:6333
- MySQL: `localhost:3307`

Dừng ứng dụng:

```powershell
docker compose down
```

## Nạp dữ liệu

Chạy trong thư mục gốc project, theo thứ tự:

```powershell
docker exec rag_api_service python -m app.pipeline.extract
docker exec rag_api_service python /app/app/pipeline/transform.py
docker exec rag_api_service python -m app.pipeline.load
```

- `extract.py` đọc sản phẩm active từ MySQL và tạo `products_data_raws.jsonl`.
- `transform.py` chia nội dung thành chunks và tạo `products_data_chunks.jsonl`.
- `load.py` tạo embedding rồi nạp dữ liệu vào collection `ecommerce_products` trong Qdrant.

Lệnh `load.py` gọi OpenAI Embeddings và có thể phát sinh chi phí API.

## API

Endpoint:

```text
POST http://localhost:8081/api/chat
```

Request tối thiểu:

```json
{
  "query": "Bạn có balo không?"
}
```

Request có bộ lọc:

```json
{
  "query": "Tìm sản phẩm thời trang dưới 1 triệu",
  "category": "thoi_trang",
  "max_price": 1000000
}
```

API trả về câu trả lời dạng streaming.

## Cấu trúc thư mục

```text
app/
  api/                 API routes
  frontend/            Giao diện chat
  pipeline/            Extract, transform, load
  schemas/             Pydantic schemas
  services/            RAG và truy vấn Qdrant
  main.py              Điểm vào FastAPI
data/
  init.sql             Schema và dữ liệu mẫu MySQL
  products_data_raws.jsonl
  products_data_chunks.jsonl
docker-compose.yml
Dockerfile
requirements.txt
```

## Xử lý lỗi thường gặp

- `401 invalid_api_key`: kiểm tra API key trong `.env`.
- `429 insufficient_quota`: kiểm tra Usage và Billing của OpenAI.
- Qdrant không tìm thấy sản phẩm: kiểm tra collection `ecommerce_products` và chạy lại pipeline load.
