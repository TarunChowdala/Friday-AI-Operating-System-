"""Text-to-speech via Edge TTS → canonical 16 kHz PCM chunks."""
from __future__ import annotations

import time
from typing import AsyncIterator

import edge_tts

from app.core.audio_pcm import mp3_to_pcm16, pcm_ms, yield_pcm_chunks
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    def __init__(self) -> None:
        logger.info("Initializing Edge TTS Pipeline...")
        self.default_voice = "en-GB-RyanNeural"
        logger.info("Edge TTS loaded successfully!")

    def _voice(self, request: TTSRequest) -> str:
        voice = self.default_voice
        if (
            request.voice
            and request.voice not in ("default",)
            and request.voice.startswith("en-")
        ):
            voice = request.voice
        return voice

    async def _mp3(self, request: TTSRequest) -> bytes:
        communicate = edge_tts.Communicate(request.text, self._voice(request))
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    async def synthesize_pcm_stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
        """Edge only emits a complete MP3; convert once, then stream PCM chunks."""
        logger.debug("Edge TTS PCM: %s...", request.text[:40])
        start = time.time()
        try:
            mp3 = await self._mp3(request)
            pcm = await mp3_to_pcm16(mp3)
        except Exception as e:
            logger.error("Edge TTS PCM failed: %s", e)
            return
        logger.info(
            "Edge TTS PCM in %dms (%dB pcm)",
            int((time.time() - start) * 1000),
            len(pcm),
        )
        async for chunk in yield_pcm_chunks(pcm):
            yield chunk

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        buf = bytearray()
        async for chunk in self.synthesize_pcm_stream(request):
            buf.extend(chunk)
        pcm = bytes(buf)
        return TTSResponse(
            audio_data=pcm or None,
            format="pcm_s16le",
            duration_ms=pcm_ms(len(pcm)),
        )
