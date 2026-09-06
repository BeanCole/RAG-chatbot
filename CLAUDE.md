# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

RAG chatbot for e-commerce product search. FastAPI backend + static HTML frontend, OpenAI for
embeddings/analysis/generation, Qdrant for vector search, MySQL as the product source of truth.
Everything runs in Docker Compose. Code comments, prompts, and log messages are in Vietnamese.

## Running

```powershell
docker compose up -d          # rag_api (8081->8080), mysql (3307->3306), qdrant (6333/6334)
docker compose ps             # all services have healthchecks; wait for "healthy"
docker compose logs -f rag_api
docker compose down
```

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`. Compose forwards `OPENAI_API_KEY`,
`QDRANT_URL`, `DATABASE_URL`, `CORS_ORIGINS`, `RERANK_ENABLED` (all with sane defaults except the
key). `rag_api` mounts `./app` + `./data` and runs uvicorn `--reload`, so Python edits hot-reload;
rebuild only when `requirements.txt` changes (`docker compose up -d --build`).

Key URLs: chat UI `http://localhost:8081/frontend/index.html`, Swagger `/docs`, health `/health`.

## Local dev / tests

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\ruff check . ; .\.venv\Scripts\ruff format --check .
.\.venv\Scripts\pytest                       # 35 tests, no network — OpenAI/Qdrant/MySQL are faked
.\.venv\Scripts\pytest tests/test_rag_service.py::test_stream_yields_sse_frames_and_done
```

Tests never hit external services: `tests/conftest.py` provides `fake_openai` / `fake_qdrant`
fixtures that monkeypatch `get_openai` / `get_qdrant` in the modules that import them; DB tests use
in-memory SQLite. CI (`.github/workflows/ci.yml`) runs ruff + pytest + a `docker build`.

## Data pipeline

Run in order inside the running container, after `docker compose up`:

```powershell
docker exec rag_api_service python -m app.pipeline.extract
docker exec rag_api_service python -m app.pipeline.transform
docker exec rag_api_service python -m app.pipeline.load     # calls OpenAI embeddings, costs money
```

- `extract.py` — `products` rows with `status='active'` from MySQL → `data/products_data_raws.jsonl`.
- `transform.py` — chunks via `app/services/chunking.py` (`RecursiveCharacterTextSplitter` 500/50)
  into `data/products_data_chunks.jsonl`, keyed by `chunk_id` so output is deterministic/ordered.
- `load.py` — `setup_collection()` (creates `ecommerce_products`, 1536-dim cosine + payload indexes
  on `metadata.price` float / `metadata.category` keyword), then batch-embeds and upserts via
  `app/services/indexing_service.py`. Point IDs are `uuid5(NAMESPACE_URL, chunk_id)` — idempotent.

Paths come from `settings.data_dir` (default `/app/data`, env-overridable to run outside Docker).

## Architecture

- `app/config.py` — single `pydantic-settings` `Settings` object (`settings`), the only place
  env/defaults live (URLs, model names, `top_k`, `rerank_enabled`, `history_max_turns`, ...).
- `app/clients.py` — lazily-cached `get_openai()` / `get_qdrant()` / `get_engine()`. Never
  construct these at import time; it breaks tests and import-without-key.
- `app/services/chunking.py` — chunking shared by pipeline + live indexing.
- `app/services/indexing_service.py` — `setup_collection`, `embed_texts` (batched, `tenacity`
  retry on `RateLimitError`/`APIError`), `upsert_chunks`, `index_product`, `delete_product_points`.
  Used by both `app.pipeline.load` and the product API so there's one embed/upsert path.
- `app/services/rag_service.py` — the chat pipeline (see below).
- `app/services/product_service.py` — MySQL CRUD that keeps Qdrant in sync via indexing_service.
- `app/api/` — `chat_router` (`/api/chat`), `product_router` (`/api/products` CRUD),
  `health_router` (`/health`).

Chat request flow (`chat_router` → `rag_service`):

1. `analyze_query()` — `chat_model` + `json_object` parses the query into a validated
   `QueryFilters` (`category` restricted to `dien_tu`/`thoi_trang`, `max_price` coerced to
   positive float or `None`). Falls back to empty filters on any error. Conversation `history`
   (last `history_max_turns`) is prepended.
2. Router precedence: an explicit `request.category` / `request.max_price` from the client wins;
   otherwise the `analyze_query` inference is used.
3. `retrieve_context()` — embeds the query, builds a Qdrant `Filter` (exact `metadata.category`,
   `Range(lte)` on `metadata.price`), `query_points`. If `rerank_enabled`, over-fetches `top_k*3`
   and an LLM call reorders/trims to `top_k`. Formats chunks; `metadata.type == 'policy'` renders
   without a price. Raises `RetrievalError` on backend failure (not swallowed).
4. `generate_answer_stream()` — yields **real SSE frames**: `data: <json-encoded token>\n\n` per
   token, then `data: [DONE]\n\n`. Tokens are JSON-encoded so newlines/quotes can't break framing.
   `RetrievalError` / streaming errors yield a fallback message + `[DONE]`.

The frontend (`app/frontend/index.html`) keeps a `history` array, posts `{query, history}` to
`${origin}/api/chat`, and parses the SSE stream by splitting on `\n\n`.

## Gotchas

- `data/init.sql` seeds MySQL only on first container creation (empty volume). Reseed:
  `docker compose down -v`.
- `.env` is gitignored and must never be committed. `.env.example` is the template.
- Generated `data/*.jsonl` are gitignored — don't commit them.
- Frontend has no build step; it's served as-is from `/frontend`.
