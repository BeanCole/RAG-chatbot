import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.chat_router import router as chat_router
from app.api.health_router import router as health_router
from app.api.product_router import router as product_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Chatbot",
    description="Chatbot hỗ trợ tìm kiếm sản phẩm bằng RAG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router, prefix="/api", tags=["Chatbot API"])
app.include_router(product_router, prefix="/api")

_frontend_dir = Path(__file__).parent / "frontend"
app.mount("/frontend", StaticFiles(directory=_frontend_dir), name="frontend")


@app.get("/")
def root():
    return {"status": "online", "message": "Welcome to my chatbot"}


logger.info("RAG Chatbot is running...")
