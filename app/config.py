"""Central application settings, loaded from environment / .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- OpenAI ---
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o-mini"
    openai_max_retries: int = 3
    openai_timeout: float = 30.0

    # --- Qdrant ---
    qdrant_url: str = "http://qdrant_db:6333"
    collection_name: str = "ecommerce_products"

    # --- MySQL ---
    database_url: str = (
        "mysql+pymysql://root:root@mysql:3306/ecommerce_db?charset=utf8mb4"
    )

    # --- Retrieval / generation ---
    top_k: int = 4
    rerank_enabled: bool = False
    history_max_turns: int = 6

    # --- Paths ---
    data_dir: str = "/app/data"

    # --- API ---
    # NoDecode: take the raw env string and split it ourselves (comma-separated)
    # instead of letting pydantic-settings try to JSON-decode it.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8081"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
