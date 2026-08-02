"""Voice STT/TTS endpoints."""
from fastapi import APIRouter, File, UploadFile

from app.core.dependencies import VoiceManagerDep
from app.models.voice import TTSRequest, TTSResponse, TranscriptionResponse

router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(manager: VoiceManagerDep, audio: UploadFile = File(...)):
    data = await audio.read()
    return await manager.transcribe(data, filename=audio.filename or "audio.wav")


@router.post("/speak", response_model=TTSResponse)
async def speak(payload: TTSRequest, manager: VoiceManagerDep):
    return await manager.synthesize(payload)
