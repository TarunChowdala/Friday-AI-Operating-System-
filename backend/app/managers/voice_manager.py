"""Coordinates STT and TTS services."""
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse, TranscriptionResponse
from app.services.elevenlabs_service import ElevenLabsTTSService
from app.services.tts_service import TTSService
from app.services.whisper_service import WhisperService

logger = get_logger(__name__)


class VoiceManager:
    def __init__(self) -> None:
        cfg = get_settings()
        self.stt = WhisperService()

        engine = (cfg.TTS_ENGINE or "edge").lower()
        if engine == "elevenlabs":
            logger.info("VoiceManager selecting ElevenLabs TTS engine")
            self.tts = ElevenLabsTTSService()
        else:
            logger.info("VoiceManager selecting Edge TTS engine")
            self.tts = TTSService()

    async def transcribe(self, audio: bytes, filename: str = "audio.wav") -> TranscriptionResponse:
        logger.debug("transcribe %s (%d bytes)", filename, len(audio))
        return await self.stt.transcribe(audio, filename=filename)

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        return await self.tts.synthesize(request)

