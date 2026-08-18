"""Speech-to-text: Groq Whisper + local Faster-Whisper. Both take canonical PCM."""
from __future__ import annotations

import asyncio
import io
import time

from faster_whisper import WhisperModel

from app.core.audio_pcm import pcm16_to_wav
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.voice import TranscriptionResponse

logger = get_logger(__name__)

_PROMPT = "JARVIS, Youtube, Amazon, Spotify, Terminal, Chrome, Google, Tarun"


class WhisperService:
    def __init__(self) -> None:
        self.cfg = get_settings()
        self.model_name = self.cfg.WHISPER_MODEL or "base"

        if self.cfg.GROQ_API_KEY:
            logger.info("Initialized Groq Cloud Whisper STT")
            from groq import AsyncGroq

            self.groq_client = AsyncGroq(api_key=self.cfg.GROQ_API_KEY)
        else:
            self.groq_client = None

        logger.info("Loading local Faster-Whisper fallback: %s...", self.model_name)
        self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully!")

    def _to_wav(
        self, audio: bytes, filename: str, audio_format: str
    ) -> tuple[bytes, str, str]:
        fmt = (audio_format or "").lower()
        name = (filename or "audio.wav").lower()
        if fmt in ("pcm_s16le", "pcm") or name.endswith(".pcm"):
            return pcm16_to_wav(audio), "audio.wav", "audio/wav"
        if name.endswith(".webm") or "webm" in fmt:
            return audio, filename or "audio.webm", "audio/webm"
        if name.endswith(".mp3") or "mp3" in fmt:
            return audio, filename or "audio.mp3", "audio/mpeg"
        return audio, filename or "audio.wav", "audio/wav"

    def _run_local_transcription(self, audio_bytes: bytes) -> tuple[str, float]:
        audio_stream = io.BytesIO(audio_bytes)
        segments, info = self.model.transcribe(
            audio_stream,
            beam_size=2,
            language="en",
            initial_prompt=_PROMPT,
        )
        segment_list = list(segments)
        full_text = " ".join([segment.text for segment in segment_list]).strip()
        prob = getattr(info, "language_probability", 1.0) if info else 1.0
        return full_text, prob

    async def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        audio_format: str = "",
    ) -> TranscriptionResponse:
        logger.debug("Transcribing audio (%d bytes, format=%s)", len(audio), audio_format)
        start_time = time.time()
        if not audio or len(audio) < 500:
            logger.debug("Audio buffer too small (%d bytes), skipping.", len(audio))
            return TranscriptionResponse(text="", confidence=0.0, duration_ms=0)

        payload, groq_name, mime = self._to_wav(audio, filename, audio_format)

        if self.groq_client:
            try:
                res = await self.groq_client.audio.transcriptions.create(
                    file=(groq_name, payload, mime),
                    model="whisper-large-v3",
                    response_format="json",
                    language="en",
                    prompt=_PROMPT,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                text = res.text.strip()
                logger.info("Groq Whisper heard (in %dms): '%s'", duration_ms, text)
                return TranscriptionResponse(text=text, confidence=0.99, duration_ms=duration_ms)
            except Exception as e:
                logger.warning("Groq Cloud Whisper failed, falling back to local: %s", e)

        try:
            full_text, confidence = await asyncio.to_thread(
                self._run_local_transcription, payload
            )
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Local Whisper heard (in %dms): '%s'", duration_ms, full_text)
            return TranscriptionResponse(
                text=full_text, confidence=confidence, duration_ms=duration_ms
            )
        except Exception as e:
            logger.error("Whisper transcription failed completely: %s", e)
            return TranscriptionResponse(text="", confidence=0.0, duration_ms=0)
