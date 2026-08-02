"""Runtime settings endpoints."""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/")
async def get_runtime_settings():
    cfg = get_settings()
    return {
        "app_name": cfg.APP_NAME,
        "version": cfg.APP_VERSION,
        "ollama_model": cfg.OLLAMA_MODEL,
        "whisper_model": cfg.WHISPER_MODEL,
        "tts_engine": cfg.TTS_ENGINE,
        "debug": cfg.DEBUG,
    }


@router.patch("/")
async def update_runtime_settings(payload: dict):
    # TODO: persist runtime overrides
    return {"updated": list(payload.keys()), "status": "stub"}
