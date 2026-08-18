"""Coordinates STT and TTS. Wire format is always 16 kHz PCM."""
from typing import AsyncIterator

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
            if engine not in ("edge", "elevenlabs"):
                logger.warning(
                    "TTS_ENGINE=%s is not implemented; using Edge. "
                    "All engines must emit pcm_s16le via synthesize_pcm_stream.",
                    engine,
                )
            logger.info("VoiceManager selecting Edge TTS engine")
            self.tts = TTSService()

    async def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        audio_format: str = "",
    ) -> TranscriptionResponse:
        logger.debug("transcribe %s (%d bytes, %s)", filename, len(audio), audio_format)
        return await self.stt.transcribe(
            audio, filename=filename, audio_format=audio_format
        )

    async def synthesize_pcm_stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
        async for chunk in self.tts.synthesize_pcm_stream(request):
            yield chunk

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        return await self.tts.synthesize(request)
