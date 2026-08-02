"""Coordinates STT and TTS services."""
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse, TranscriptionResponse
from app.services.tts_service import TTSService
from app.services.whisper_service import WhisperService

logger = get_logger(__name__)


class VoiceManager:
    def __init__(self) -> None:
        self.stt = WhisperService()
        self.tts = TTSService()

    async def transcribe(self, audio: bytes, filename: str = "audio.wav") -> TranscriptionResponse:
        logger.debug("transcribe %s (%d bytes)", filename, len(audio))
        return await self.stt.transcribe(audio, filename=filename)

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        return await self.tts.synthesize(request)
