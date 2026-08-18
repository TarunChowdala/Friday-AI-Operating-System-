"""Canonical voice wire format: 16 kHz mono signed 16-bit little-endian PCM.

STT and TTS engines all convert to/from this. No Deepgram required.
"""
from __future__ import annotations

import asyncio
import io
import shutil
import wave
from typing import AsyncIterator

from app.core.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE
from app.core.logger import get_logger
from app.utils.audio import pcm_duration_ms

logger = get_logger(__name__)

PCM_SAMPLE_RATE = DEFAULT_SAMPLE_RATE
PCM_CHANNELS = DEFAULT_CHANNELS
PCM_SAMPLE_WIDTH = 2
# 100ms of audio — small enough to start playback before the rest arrives.
PCM_CHUNK_BYTES = int(PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * PCM_CHANNELS * 0.1)


def pcm16_to_wav(pcm: bytes, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(PCM_CHANNELS)
        wf.setsampwidth(PCM_SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def iter_pcm_chunks(pcm: bytes, chunk_bytes: int = PCM_CHUNK_BYTES) -> list[bytes]:
    if not pcm:
        return []
    return [pcm[i : i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]


async def mp3_to_pcm16(mp3: bytes, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    """Decode MP3 (Edge) to canonical PCM via ffmpeg."""
    if not mp3:
        return b""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to convert MP3 TTS to PCM")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "mp3",
        "-i",
        "pipe:0",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        str(PCM_CHANNELS),
        "-ar",
        str(sample_rate),
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(mp3)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mp3→pcm failed: {(err or b'').decode()[:300]}")
    return out


async def yield_pcm_chunks(pcm: bytes) -> AsyncIterator[bytes]:
    for chunk in iter_pcm_chunks(pcm):
        if chunk:
            yield chunk


def pcm_ms(num_bytes: int, sample_rate: int = PCM_SAMPLE_RATE) -> int:
    return pcm_duration_ms(num_bytes, sample_rate, PCM_CHANNELS, PCM_SAMPLE_WIDTH)
