"""Text-to-speech service via Edge TTS."""
import time
import edge_tts

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    def __init__(self) -> None:
        logger.info("Initializing Edge TTS Pipeline...")
        # 'en-US-AriaNeural' is a highly realistic, crisp female voice from Microsoft
        self.default_voice = "en-US-AvaNeural" 
        logger.info("Edge TTS loaded successfully!")

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Asynchronously synthesizes text into audio bytes."""
        logger.debug("Synthesizing speech: %s...", request.text[:40])
        start_time = time.time()
        
        try:
            # Edge-TTS streams audio natively in pure python async!
            communicate = edge_tts.Communicate(request.text, self.default_voice)
            
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("TTS generated audio in %dms", duration_ms)
            
            return TTSResponse(
                audio_data=audio_bytes, 
                format="mp3", 
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error("Edge TTS failed: %s", e)
            return TTSResponse(audio_data=None, format="mp3", duration_ms=0)

