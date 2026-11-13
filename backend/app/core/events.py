"""Application lifecycle hooks."""
import httpx
from pathlib import Path

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.redis_client import close_redis, ping_redis
from app.database.database import init_db

logger = get_logger(__name__)


async def on_startup() -> None:
    cfg = get_settings()
    
    # 1. Validate configuration & Initialize paths
    for path in (cfg.LOGS_PATH, cfg.UPLOADS_PATH, cfg.CONVERSATIONS_PATH, cfg.VECTOR_STORE_PATH):
        Path(path).mkdir(parents=True, exist_ok=True)
    logger.info("JARVIS backend starting — v%s", cfg.APP_VERSION)
    
    # 2. Initialize Database
    logger.info("Initializing Database...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error("Database init failed: %s", e)

    # 3. Redis (live session store)
    logger.info("Checking Redis at %s ...", cfg.REDIS_URL)
    try:
        if await ping_redis():
            logger.info("Redis is ready (live Session Manager).")
        else:
            logger.error("Redis ping returned false.")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        
    # 4. Verify Ollama server is running
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

    # 5. Register available tools
    logger.info("Registering agent tools...")
    # TODO: Import and map tool classes
    
    # 6. Initialize application state
    logger.info("Application state initialized and ready.")


async def on_shutdown() -> None:
    logger.info("JARVIS backend shutting down")
    try:
        from app.tools.jucce.tools import close_jucce

        close_jucce()
    except Exception as e:
        logger.debug("JUCCE shutdown cleanup skipped: %s", e)

    try:
        from app.tools.playwright_mcp import close_playwright_mcp

        close_playwright_mcp()
    except Exception as e:
        logger.debug("Playwright MCP shutdown cleanup skipped: %s", e)
    await close_redis()
