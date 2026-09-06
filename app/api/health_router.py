import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.clients import get_engine, get_qdrant
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Kiểm tra tình trạng các dịch vụ phụ thuộc")
def health():
    result: dict[str, object] = {"status": "ok"}

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        result["mysql"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("mysql health check failed: %s", exc)
        result["mysql"] = "error"
        result["status"] = "degraded"

    try:
        client = get_qdrant()
        if client.collection_exists(settings.collection_name):
            count = client.count(settings.collection_name, exact=True).count
            result["qdrant"] = {"collection": settings.collection_name, "points": count}
        else:
            result["qdrant"] = {"collection": settings.collection_name, "points": 0}
            result["status"] = "degraded"
    except Exception as exc:  # noqa: BLE001
        logger.warning("qdrant health check failed: %s", exc)
        result["qdrant"] = "error"
        result["status"] = "degraded"

    return result
