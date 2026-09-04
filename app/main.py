from fastapi import FastAPI
import logging
from app.api.chat_router import router as chat_router
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Chatbot",
    description="Chatbot that support searching products",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(chat_router, prefix="/api", tags=["Chatbot API"])

@app.get("/")
def test():
    return {
        "status": "online",
        "message": "Welcome to my chatbot"
    }

logger.info("RAG Chatbot is running...")