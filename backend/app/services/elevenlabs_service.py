"""ElevenLabs TTS → canonical 16 kHz PCM chunks (HTTP stream, same interface as Edge)."""
from __future__ import annotations

import time
from typing import AsyncIterator

import httpx

from app.core.audio_pcm import PCM_CHUNK_BYTES, mp3_to_pcm16, pcm_ms, yield_pcm_chunks
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class ElevenLabsTTSService:
    def __init__(self) -> None:
        cfg = get_settings()
        self.api_key = cfg.ELEVENLABS_API_KEY
        self.default_voice_id = cfg.ELEVENLABS_VOICE_ID
        self.model_id = cfg.ELEVENLABS_MODEL_ID
        self.base_url = "https://api.elevenlabs.io/v1"

        if self.api_key:
            logger.info(
                "Initialized ElevenLabs TTS Service (Voice ID: %s, Model: %s)",
                self.default_voice_id,
                self.model_id,
            )
        else:
            logger.warning(
                "ElevenLabs API Key not set (ELEVENLABS_API_KEY is missing). "
                "Calls to ElevenLabs TTS will fail unless key is configured."
            )

    def _voice_id(self, request: TTSRequest) -> str:
        voice_id = self.default_voice_id
        if (
            request.voice
            and request.voice not in ("default", "en-US-AriaNeural")
            and not request.voice.startswith("en-")
        ):
            voice_id = request.voice
        return voice_id

    def _payload(self, request: TTSRequest) -> dict:
        return {
            "text": request.text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

    async def synthesize_pcm_stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
        """Prefer PCM HTTP stream; fall back to MP3 → PCM so the wire format stays PCM."""
        if not self.api_key:
            logger.error("ElevenLabs TTS requested but ELEVENLABS_API_KEY is not configured.")
            return

        logger.debug("ElevenLabs PCM stream: %s...", request.text[:40])
        start = time.time()
        voice_id = self._voice_id(request)
        url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/octet-stream",
        }
        params = {"output_format": "pcm_16000"}
        got_any = False

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                async with client.stream(
                    "POST", url, json=self._payload(request), headers=headers, params=params
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread())[:500]
                        logger.warning(
                            "ElevenLabs PCM stream HTTP %d: %s — falling back to MP3",
                            response.status_code,
                            body,
                        )
                    else:
                        buffer = b""
                        async for piece in response.aiter_bytes():
                            if not piece:
                                continue
                            buffer += piece
                            while len(buffer) >= PCM_CHUNK_BYTES:
                                got_any = True
                                yield buffer[:PCM_CHUNK_BYTES]
                                buffer = buffer[PCM_CHUNK_BYTES:]
                        if buffer:
                            got_any = True
                            yield buffer
                        logger.info(
                            "ElevenLabs PCM stream in %dms",
                            int((time.time() - start) * 1000),
                        )
                        return
        except Exception as e:
            logger.warning("ElevenLabs PCM stream failed (%s) — MP3 fallback", e)

        # Same character quota, just not streamed: MP3 then ffmpeg → PCM chunks.
        try:
            pcm = await self._mp3_then_pcm(request)
        except Exception as e:
            logger.error("ElevenLabs TTS failed: %s", e)
            return
        if not got_any:
            logger.info(
                "ElevenLabs MP3→PCM in %dms (%dB)",
                int((time.time() - start) * 1000),
                len(pcm),
            )
        async for chunk in yield_pcm_chunks(pcm):
            yield chunk

    async def _mp3_then_pcm(self, request: TTSRequest) -> bytes:
        url = f"{self.base_url}/text-to-speech/{self._voice_id(request)}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=self._payload(request), headers=headers)
            response.raise_for_status()
            return await mp3_to_pcm16(response.content)

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
