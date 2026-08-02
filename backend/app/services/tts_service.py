"""Text-to-speech service (stub)."""
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    def __init__(self) -> None:
        self.engine = get_settings().TTS_ENGINE

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        logger.debug("tts stub (%s): %s…", self.engine, request.text[:40])
        # TODO: edge-tts / piper integration → write to storage/uploads
        return TTSResponse(audio_url=None, format="mp3", duration_ms=0)
