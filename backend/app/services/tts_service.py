"""Text-to-speech service via Edge TTS.

LIMITATION: Edge returns a complete MP3 for each synthesize() call. We buffer
provider stream chunks into one valid MP3 before sending to the browser because
decodeAudioData requires a complete file. Latency is reduced by calling
synthesize() per sentence/phrase (see websocket sentence flusher), not by
byte-streaming incomplete MP3 frames to the client.
"""
import time

import edge_tts

from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    def __init__(self) -> None:
        logger.info("Initializing Edge TTS Pipeline...")
        self.default_voice = "en-US-ChristopherNeural"
        logger.info("Edge TTS loaded successfully!")

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize one phrase into a complete MP3 (Edge stream → single buffer)."""
        logger.debug("Synthesizing speech: %s...", request.text[:40])
        start_time = time.time()
        voice = self.default_voice
        if (
            request.voice
            and request.voice not in ("default",)
            and request.voice.startswith("en-")
        ):
            voice = request.voice

        try:
            communicate = edge_tts.Communicate(request.text, voice)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("TTS generated audio in %dms", duration_ms)
            return TTSResponse(
                audio_data=audio_bytes, format="mp3", duration_ms=duration_ms
            )
        except Exception as e:
            logger.error("Edge TTS failed: %s", e)
            return TTSResponse(audio_data=None, format="mp3", duration_ms=0)
