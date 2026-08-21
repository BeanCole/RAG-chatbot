from fastapi import FastAPI
import logging

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

@app.get("/")
def test():
    return {
        "status": "online",
        "message": "Welcome to my chatbot"
    }

logger.info("RAG Chatbot is running...")