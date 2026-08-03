"""Application settings loaded from environment."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "FRIDAY AI"
    APP_VERSION: str = "4.2.1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    WHISPER_MODEL: str = "base"
    TTS_ENGINE: str = "edge"  # edge | piper | pyttsx3

    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/friday.db"
    VECTOR_STORE_PATH: str = "./storage/embeddings"
    CONVERSATIONS_PATH: str = "./storage/conversations"
    UPLOADS_PATH: str = "./storage/uploads"
    LOGS_PATH: str = "./storage/logs"

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
