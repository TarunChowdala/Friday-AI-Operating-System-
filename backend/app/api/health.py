"""Health check endpoints."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.constants import APP_NAME, APP_VERSION

router = APIRouter()


@router.get("/")
async def health():
    cfg = get_settings()
    return {
        "status": "ok",
        "system": APP_NAME,
        "version": APP_VERSION,
        "debug": cfg.DEBUG,
    }


@router.get("/ready")
async def readiness():
    # TODO: check Ollama, DB, vector store
    return {"ready": True}
