"""Lazily-constructed shared clients.

Building these at import time makes the modules impossible to import without a
valid API key (and hard to test), so we defer construction until first use.
"""

from functools import lru_cache

from openai import OpenAI
from qdrant_client import QdrantClient
from sqlalchemy import Engine, create_engine

from app.config import settings


@lru_cache
def get_openai() -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        max_retries=settings.openai_max_retries,
        timeout=settings.openai_timeout,
    )


@lru_cache
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


@lru_cache
def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)
