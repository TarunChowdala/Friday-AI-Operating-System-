"""Application lifecycle hooks."""
import httpx
from pathlib import Path

from app.core.config import get_settings
from app.core.logger import get_logger
from app.database.database import init_db

logger = get_logger(__name__)


async def on_startup() -> None:
    cfg = get_settings()
    
    # 1. Validate configuration & Initialize paths
    for path in (cfg.LOGS_PATH, cfg.UPLOADS_PATH, cfg.CONVERSATIONS_PATH, cfg.VECTOR_STORE_PATH):
        Path(path).mkdir(parents=True, exist_ok=True)
    logger.info("FRIDAY backend starting — v%s", cfg.APP_VERSION)
    
    # 2. Initialize Database
    logger.info("Initializing Database...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error("Database init failed: %s", e)
        
    # 3. Verify Ollama server is running
    logger.info("Checking Ollama server status...")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                logger.info("Ollama is running! Available models: %s", ", ".join(models))
            else:
                logger.warning("Ollama server responded with status: %s", resp.status_code)
    except Exception as e:
        logger.error("Failed to connect to Ollama server at http://127.0.0.1:11434: %s", e)

    # 4. Register available tools
    logger.info("Registering agent tools...")
    # TODO: Import and map tool classes
    
    # 5. Initialize application state
    logger.info("Application state initialized and ready.")


async def on_shutdown() -> None:
    logger.info("FRIDAY backend shutting down")
    # TODO: flush memory, close WS connections, dispose DB
