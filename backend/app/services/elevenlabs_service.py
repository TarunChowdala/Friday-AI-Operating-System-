"""ElevenLabs Text-to-Speech service integration."""
import time
import httpx

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

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Asynchronously synthesizes text into audio bytes using ElevenLabs API.

        LIMITATION: ElevenLabs non-streaming HTTP endpoint — full MP3 body is
        buffered before return. Cancellation mid-request is not supported; barge-in
        drops late chunks on the frontend via ignoreTts.
        """
        if not self.api_key:
            logger.error("ElevenLabs TTS requested but ELEVENLABS_API_KEY is not configured.")
            return TTSResponse(audio_data=None, format="mp3", duration_ms=0)

        logger.debug("Synthesizing speech via ElevenLabs: %s...", request.text[:40])
        start_time = time.time()

        voice_id = self.default_voice_id
        if (
            request.voice
            and request.voice not in ("default", "en-US-AriaNeural")
            and not request.voice.startswith("en-")
        ):
            voice_id = request.voice

        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": request.text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error(
                        "ElevenLabs API Error HTTP %d: %s | URL: %s | Payload: %s",
                        response.status_code,
                        response.text,
                        url,
                        payload,
                    )
                response.raise_for_status()
                audio_bytes = response.content

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("ElevenLabs TTS generated audio in %dms", duration_ms)

            return TTSResponse(
                audio_data=audio_bytes,
                format="mp3",
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error("ElevenLabs TTS synthesis failed: %s", e)
            return TTSResponse(audio_data=None, format="mp3", duration_ms=0)
