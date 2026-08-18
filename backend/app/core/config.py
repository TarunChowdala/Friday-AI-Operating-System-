"""Application settings loaded from environment."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "JARVIS AI"
    APP_VERSION: str = "4.2.1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Primary chat/tool LLM: ollama | groq | gemini
    LLM_PROVIDER: str = "ollama"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str | None = None

    EMBEDDING_MODEL: str = "nomic-embed-text"

    WHISPER_MODEL: str = "base"
    TTS_ENGINE: str = "edge"  # edge | elevenlabs | piper | pyttsx3

    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Default Rachel voice / or custom voice
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"

    DATABASE_URL: str = "postgresql+asyncpg://friday:friday@127.0.0.1:5432/friday"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    SESSION_TTL_SECONDS: int = 86400  # 24h idle live-session expiry
    SESSION_MAX_MESSAGES: int = 40
    VECTOR_STORE_PATH: str = "./storage/embeddings"
    CONVERSATIONS_PATH: str = "./storage/conversations"
    UPLOADS_PATH: str = "./storage/uploads"
    LOGS_PATH: str = "./storage/logs"

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
