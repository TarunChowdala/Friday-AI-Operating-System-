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
        self.cfg = get_settings()
        self.model_name = self.cfg.WHISPER_MODEL or "base"
        
        if self.cfg.GROQ_API_KEY:
            logger.info("⚡ Initialized Groq Cloud Whisper STT (distil-whisper-large-v3-en)")
            from groq import AsyncGroq
            self.groq_client = AsyncGroq(api_key=self.cfg.GROQ_API_KEY)
        else:
            self.groq_client = None

        logger.info("Loading Local Faster-Whisper model fallback: %s...", self.model_name)
        self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully!")

    def _run_local_transcription(self, audio_bytes: bytes) -> tuple[str, float]:
        """Fallback local Whisper transcription."""
        audio_stream = io.BytesIO(audio_bytes)
        segments, info = self.model.transcribe(
            audio_stream, 
            beam_size=2, 
            language="en",
            initial_prompt="JARVIS, Youtube, Amazon, Spotify, Terminal, Chrome, Google, Tarun"
        )
        segment_list = list(segments)
        full_text = " ".join([segment.text for segment in segment_list]).strip()
        prob = getattr(info, 'language_probability', 1.0) if info else 1.0
        return full_text, prob

    async def transcribe(self, audio: bytes, filename: str = "audio.wav") -> TranscriptionResponse:
        """Asynchronously transcribes audio bytes into text."""
        logger.debug("Transcribing audio (%d bytes)", len(audio))
        start_time = time.time()
        
        # Skip empty or header-only audio buffers
        if not audio or len(audio) < 1000:
            logger.debug("Audio buffer too small (%d bytes), skipping transcription.", len(audio))
            return TranscriptionResponse(text="", confidence=0.0, duration_ms=0)

        # ⚡ 1. Try Groq Cloud Whisper first (Sub-100ms, highest accuracy)
        if self.groq_client:
            try:
                res = await self.groq_client.audio.transcriptions.create(
                    file=(filename, audio, "audio/wav"),
                    model="whisper-large-v3",
                    response_format="json",
                    language="en",

                    prompt="JARVIS, Youtube, Amazon, Spotify, Terminal, Chrome, Google, Tarun"
                )
                duration_ms = int((time.time() - start_time) * 1000)
                text = res.text.strip()
                logger.info("⚡ Groq Whisper heard (in %dms): '%s'", duration_ms, text)
                return TranscriptionResponse(text=text, confidence=0.99, duration_ms=duration_ms)
            except Exception as e:
                logger.warning("Groq Cloud Whisper failed, falling back to local Whisper: %s", e)

        # 💻 2. Fallback to Local Faster-Whisper
        try:
            full_text, confidence = await asyncio.to_thread(self._run_local_transcription, audio)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Local Whisper heard (in %dms): '%s'", duration_ms, text if 'text' in locals() else full_text)
            return TranscriptionResponse(text=full_text, confidence=confidence, duration_ms=duration_ms)
        except Exception as e:
            logger.error("Whisper transcription failed completely: %s", e)
            return TranscriptionResponse(text="", confidence=0.0, duration_ms=0)


