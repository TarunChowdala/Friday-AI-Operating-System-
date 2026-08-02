"""Speech-to-text via Whisper (stub)."""
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TranscriptionResponse

logger = get_logger(__name__)


class WhisperService:
    def __init__(self) -> None:
        self.model_name = get_settings().WHISPER_MODEL

    async def transcribe(self, audio: bytes, filename: str = "audio.wav") -> TranscriptionResponse:
        logger.debug("whisper stub: %s (%d bytes)", filename, len(audio))
        # TODO: load whisper model / call faster-whisper
        return TranscriptionResponse(text="[stub transcription]", confidence=0.0, duration_ms=0)
