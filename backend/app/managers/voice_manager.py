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
        self.fallback_tts = TTSService()

        engine = (cfg.TTS_ENGINE or "edge").lower()
        if engine == "elevenlabs":
            logger.info("VoiceManager selecting ElevenLabs TTS engine (Edge as fallback)")
            self.tts = ElevenLabsTTSService()
        else:
            if engine not in ("edge", "elevenlabs"):
                logger.warning(
                    "TTS_ENGINE=%s is not implemented; using Edge. "
                    "All engines must emit pcm_s16le via synthesize_pcm_stream.",
                    engine,
                )
            logger.info("VoiceManager selecting Edge TTS engine")
            self.tts = self.fallback_tts

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
        emitted_any = False
        try:
            async for chunk in self.tts.synthesize_pcm_stream(request):
                emitted_any = True
                yield chunk
        except Exception as e:
            logger.warning("Primary TTS engine stream error: %s", e)

        # Fallback to Edge TTS if primary (ElevenLabs) yielded 0 audio bytes (e.g. quota/auth error)
        if not emitted_any and self.tts != self.fallback_tts:
            logger.warning("Primary TTS yielded 0 audio bytes. Silently falling back to Edge TTS.")
            try:
                async for chunk in self.fallback_tts.synthesize_pcm_stream(request):
                    yield chunk
            except Exception as e:
                logger.error("Edge TTS fallback also failed: %s", e)

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        try:
            res = await self.tts.synthesize(request)
            if res.audio_data and len(res.audio_data) > 0:
                return res
        except Exception as e:
            logger.warning("Primary TTS synthesize failed: %s", e)

        if self.tts != self.fallback_tts:
            logger.warning("Falling back to Edge TTS for synthesize.")
            return await self.fallback_tts.synthesize(request)
        return res
