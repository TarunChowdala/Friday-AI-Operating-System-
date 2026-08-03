"""Speech-to-text via Faster-Whisper."""
import io
import time
import asyncio
from faster_whisper import WhisperModel

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TranscriptionResponse

logger = get_logger(__name__)

class WhisperService:
    def __init__(self) -> None:
        self.model_name = get_settings().WHISPER_MODEL or "base"
        logger.info("Loading Faster-Whisper model: %s...", self.model_name)
        
        # Load the model into memory once.
        # Uses CPU with int8 quantization to save RAM, but runs incredibly fast.
        # If you have an NVIDIA GPU, you can change device="cuda" and compute_type="float16"
        self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully!")

    def _run_transcription(self, audio_bytes: bytes) -> tuple[str, float]:
        """Synchronous wrapper for Faster-Whisper execution."""
        audio_stream = io.BytesIO(audio_bytes)
        # beam_size=5 provides a good balance between accuracy and speed
        segments, info = self.model.transcribe(audio_stream, beam_size=5)
        
        # segments is a generator, so we iterate through it to build the full string
        full_text = " ".join([segment.text for segment in segments]).strip()
        return full_text, info.language_probability

    async def transcribe(self, audio: bytes, filename: str = "audio.wav") -> TranscriptionResponse:
        """Asynchronously transcribes audio bytes into text."""
        logger.debug("Transcribing audio (%d bytes)", len(audio))
        start_time = time.time()
        
        try:
            # We run this in a separate thread so it doesn't freeze the WebSocket loop!
            full_text, confidence = await asyncio.to_thread(self._run_transcription, audio)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Whisper heard (in %dms): '%s'", duration_ms, full_text)
            
            return TranscriptionResponse(
                text=full_text, 
                confidence=confidence, 
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error("Whisper transcription failed: %s", e)
            return TranscriptionResponse(text="", confidence=0.0, duration_ms=0)

