"""Voice / STT / TTS schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    language: Optional[str] = None
    session_id: Optional[str] = None


class TranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    confidence: float = 0.0
    duration_ms: int = 0


class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-AriaNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


class TTSResponse(BaseModel):
    audio_url: Optional[str] = None
    format: str = "mp3"
    duration_ms: int = 0
