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
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_RESEARCH_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str | None = None
    SERPER_API_KEY: str | None = None

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

    # JUCCE is opt-in until a native desktop MCP server is installed and verified.
    JUCCE_ENABLED: bool = False
    JUCCE_LINUX_COMMAND: str = "computer-use-linux"
    JUCCE_LINUX_ARGS: str = "mcp"
    JUCCE_MCP_TIMEOUT_SECONDS: float = 15.0

    # Playwright MCP browser automation settings
    PLAYWRIGHT_MCP_ENABLED: bool = True
    PLAYWRIGHT_MCP_COMMAND: str = "npx"
    PLAYWRIGHT_MCP_ARGS: str = "-y @playwright/mcp@latest"
    PLAYWRIGHT_MCP_TIMEOUT_SECONDS: float = 30.0

    # Secret confirmation code for dangerous actions (spoken by user to approve)
    CONFIRM_CODE: str = "7989"


@lru_cache
def get_settings() -> Settings:
    return Settings()
