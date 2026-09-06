# RAG Chatbot E-commerce

[![CI](https://github.com/BeanCole/RAG-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/BeanCole/RAG-chatbot/actions/workflows/ci.yml)

Chatbot tìm kiếm sản phẩm bằng Retrieval-Augmented Generation (RAG): FastAPI, OpenAI, Qdrant, MySQL.

> **EN:** A Vietnamese e-commerce product-search chatbot. A FastAPI service turns a natural-language
> question into structured filters with an LLM, runs a metadata-filtered vector search in Qdrant,
> and streams a grounded answer back over Server-Sent Events. Products live in MySQL and are kept
> in sync with the vector index. Runs entirely on Docker Compose.

## Tính năng

- Semantic search sản phẩm, lọc trước theo danh mục và giá tối đa (metadata pre-filtering).
- LLM phân tích câu hỏi tiếng Việt → filter có cấu trúc (hiểu "10 củ", "500k", "dưới 2 triệu").
- Trả lời streaming qua SSE, hỗ trợ hội thoại nhiều lượt (gửi kèm `history`).
- (Tùy chọn) rerank kết quả truy hồi bằng LLM.
- API quản trị sản phẩm (`POST/PUT/DELETE`) tự động re-index sang Qdrant.
- Endpoint `/health` kiểm tra MySQL + Qdrant. Pipeline ETL: MySQL → JSONL → chunks → embeddings.
- Giao diện chat tĩnh phục vụ trực tiếp bởi FastAPI.

## Kiến trúc

```text
MySQL ──extract──> raws.jsonl ──transform──> chunks.jsonl ──load──> OpenAI embeddings ──> Qdrant
                                                                          ▲
  Browser ──> FastAPI /api/chat ──> analyze_query (LLM) ──> retrieve_context ──┘──> stream (SSE)
```

- **FastAPI** – API chat, quản trị sản phẩm, health, và phục vụ frontend.
- **MySQL** – nguồn sự thật cho sản phẩm.
- **Qdrant** – vector embedding + tìm kiếm ngữ nghĩa (payload index trên `price`, `category`).
- **OpenAI** – `text-embedding-3-small` cho embedding, `gpt-4o-mini` cho phân tích/sinh câu trả lời.

## Yêu cầu

- Docker Desktop đang chạy.
- OpenAI API key còn quota.

```powershell
Copy-Item .env.example .env
# rồi điền OPENAI_API_KEY vào .env
```

`.env` không bao giờ được commit.

## Chạy ứng dụng

```powershell
docker compose up -d
docker compose ps        # chờ tới khi các service ở trạng thái "healthy"
docker compose down
```

Các địa chỉ:

- Giao diện chat: <http://localhost:8081/frontend/index.html>
- Swagger: <http://localhost:8081/docs>
- Health: <http://localhost:8081/health>
- Qdrant: <http://localhost:6333> · MySQL: `localhost:3307`

## Nạp dữ liệu

Chạy theo thứ tự, bên trong container đang chạy:

```powershell
docker exec rag_api_service python -m app.pipeline.extract
docker exec rag_api_service python -m app.pipeline.transform
docker exec rag_api_service python -m app.pipeline.load     # gọi OpenAI Embeddings, phát sinh chi phí
```

`load` tạo collection `ecommerce_products`, batch-embed các chunk rồi upsert vào Qdrant. Point ID
là `uuid5(chunk_id)` nên chạy lại là idempotent.

## API

### Chat — `POST /api/chat`

```json
{
  "query": "Tìm sản phẩm thời trang dưới 1 triệu",
  "category": "thoi_trang",
  "max_price": 1000000,
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }]
}
```

Chỉ `query` là bắt buộc. `category` / `max_price` do client gửi sẽ ghi đè kết quả phân tích tự
động. Phản hồi là luồng SSE: mỗi frame `data: "<token>"\n\n`, kết thúc bằng `data: [DONE]\n\n`.

### Quản trị sản phẩm

| Method | Path | Tác dụng |
|---|---|---|
| `POST` | `/api/products` | Thêm sản phẩm vào MySQL + index sang Qdrant |
| `PUT` | `/api/products/{id}` | Cập nhật + re-index (xoá point cũ, embed lại) |
| `DELETE` | `/api/products/{id}` | Soft delete (`status='inactive'`) + xoá point Qdrant |

## Phát triển & kiểm thử

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\ruff check .
.\.venv\Scripts\pytest
```

Test không gọi mạng: OpenAI / Qdrant / MySQL đều được fake (xem `tests/conftest.py`). CI chạy
`ruff` + `pytest` + `docker build` trên mỗi push/PR.

## Design decisions

- **Metadata pre-filtering**: lọc `category` / `price` ngay trong Qdrant (payload index) trước khi
  so khớp vector → kết quả đúng ràng buộc giá/danh mục, không phụ thuộc việc LLM "tự suy luận".
- **LLM trích xuất filter**: tách bước hiểu ý định (giá, danh mục) khỏi bước sinh câu trả lời, cho
  phép người dùng hỏi tự nhiên bằng tiếng lóng tiền tệ.
- **Batch embedding + retry**: pipeline gửi cả batch trong 1 request và `tenacity` backoff khi gặp
  `RateLimitError` → nạp dữ liệu nhanh và bền hơn.
- **SSE thật + JSON-encode token**: token được `json.dumps` nên xuống dòng / dấu ngoặc trong nội
  dung không phá vỡ khung SSE.
- **Reranking là tùy chọn** (`RERANK_ENABLED`): over-fetch rồi để LLM xếp lại — đánh đổi thêm
  latency/chi phí lấy độ chính xác, mặc định tắt.
- **Một đường index dùng chung**: `indexing_service` được cả batch pipeline lẫn API sản phẩm gọi,
  tránh lệch logic chunk/embed giữa hai nơi.

## Xử lý lỗi thường gặp

- `401 invalid_api_key` / `429 insufficient_quota`: kiểm tra `OPENAI_API_KEY`, Usage & Billing.
- `/health` báo `degraded`: xem `qdrant.points` — nếu 0 thì chạy lại pipeline `load`.
- Sửa `.env` xong không có tác dụng: `docker compose up -d` lại để nạp biến môi trường mới.
