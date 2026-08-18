"""WebSocket API routes — supports barge-in interrupt while Friday is speaking."""
from __future__ import annotations

import asyncio
import base64
import re
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.router import AgentRouter
from app.core.logger import get_logger
from app.managers.voice_manager import VoiceManager
from app.models.voice import TTSRequest
from app.websocket.connection_manager import ConnectionManager

router = APIRouter()
logger = get_logger(__name__)

ws_manager = ConnectionManager()
voice_manager = VoiceManager()
agent_router = AgentRouter()


def _now_ms() -> int:
    return int(time.time() * 1000)

# Prefer not to TTS tiny crumbs; flush early on natural breaks.
_MIN_FLUSH = 12
_SOFT_FLUSH = 48  # comma/semicolon after this many chars
_HARD_FLUSH = 110  # force a speakable chunk


def _pop_speakable(buffer: str) -> tuple[str | None, str]:
    """Extract next speakable phrase from stream buffer. Returns (phrase|None, remainder)."""
    if not buffer or not buffer.strip():
        return None, buffer

    # Strong sentence end
    m = re.search(r"[^.!?\n]+[.!?]+(?:\s+|$)|.+\n", buffer)
    if m and len(m.group(0).strip()) >= _MIN_FLUSH:
        phrase = m.group(0).strip()
        rest = buffer[m.end() :]
        return phrase, rest

    # Soft break: clause after enough content
    if len(buffer.strip()) >= _SOFT_FLUSH:
        for sep in (", ", "; ", " — ", " - "):
            idx = buffer.rfind(sep)
            if idx >= _MIN_FLUSH:
                phrase = buffer[: idx + len(sep)].strip()
                rest = buffer[idx + len(sep) :]
                if len(phrase) >= _MIN_FLUSH:
                    return phrase, rest

    # Hard length cap so first audio isn't blocked by long run-ons
    if len(buffer.strip()) >= _HARD_FLUSH:
        # break at last space before hard limit
        cut = buffer.rfind(" ", 0, _HARD_FLUSH)
        if cut < _MIN_FLUSH:
            cut = _HARD_FLUSH
        phrase = buffer[:cut].strip()
        rest = buffer[cut:]
        if phrase:
            return phrase, rest

    return None, buffer


async def _speak_and_send(
    client_id: str,
    text: str,
    *,
    pipeline_start: float,
    first_audio_sent: list[bool],
    tts_total: list[float],
    first_sentence_logged: list[bool],
    agent_stream_start: float,
) -> bool:
    """Synthesize one phrase and send. Returns False if interrupted."""
    text = (text or "").strip()
    if not text:
        return True
    if ws_manager.is_interrupted(client_id):
        return False

    if not first_sentence_logged[0]:
        first_sentence_logged[0] = True
        logger.info(
            "⏱️ [LATENCY] Time-To-First-Sentence: %.3fs",
            time.time() - agent_stream_start,
        )

    logger.info("BOT SPEAK [%d chars]: %s", len(text), text)
    await ws_manager.send(
        client_id,
        {"type": "ai_text_chunk", "payload": text, "t_sent_ms": _now_ms()},
    )

    tts_start = time.time()
    tts_req = TTSRequest(text=text, voice="default")
    pcm_bytes = 0
    chunk_n = 0
    try:
        async for pcm_chunk in voice_manager.synthesize_pcm_stream(tts_req):
            if ws_manager.is_interrupted(client_id):
                return False
            if not pcm_chunk:
                continue
            chunk_n += 1
            pcm_bytes += len(pcm_chunk)
            if not first_audio_sent[0]:
                first_audio_sent[0] = True
                logger.info(
                    "⏱️ [LATENCY] TTS first PCM: %.3fs (chars=%d chunk=%dB)",
                    time.time() - tts_start,
                    len(text),
                    len(pcm_chunk),
                )
                logger.info(
                    "⚡ [LATENCY] Time-To-First-Audio (TTFA): %.3fs",
                    time.time() - pipeline_start,
                )
            await ws_manager.send(
                client_id,
                {
                    "type": "ai_audio_chunk",
                    "payload": base64.b64encode(pcm_chunk).decode("utf-8"),
                    "format": "pcm_s16le",
                    "sample_rate": 16000,
                    "t_sent_ms": _now_ms(),
                    "chars": len(text),
                },
            )
    except Exception as e:
        logger.error("TTS PCM stream failed: %s", e)
        return False

    tts_total[0] += time.time() - tts_start
    logger.info(
        "⏱️ [LATENCY] TTS stream done: %.3fs (chars=%d pcm=%dB chunks=%d) text=%s",
        time.time() - tts_start,
        len(text),
        pcm_bytes,
        chunk_n,
        text[:80],
    )
    return True


async def _handle_turn(
    client_id: str,
    user_text: str,
    stt_time: float,
    pipeline_start: float,
    *,
    vad_silence_ms: float | None = None,
    speech_ms: float | None = None,
) -> None:
    """Run one user→agent→TTS turn; exits early if interrupted."""
    from app.managers.session_manager import session_manager

    try:
        if vad_silence_ms is not None:
            logger.info("⏱️ [LATENCY] VAD/end-of-speech delay: %.0fms", vad_silence_ms)
        if speech_ms is not None:
            logger.info("⏱️ [LATENCY] User speech duration: %.0fms", speech_ms)

        logger.info("USER: %s", user_text)
        redis_start = time.time()
        live = await session_manager.append_message(client_id, "user", user_text)
        logger.info(
            "⏱️ [LATENCY] Redis append_user: %.3fs", time.time() - redis_start
        )
        session_id = live["session_id"]
        logger.info("Redis session=%s msgs=%d", session_id, len(live["messages"]))

        router_ctx = {
            "recent_messages": live.get("messages") or [],
            "focused": live.get("focused_target"),
        }
        router_start = time.time()
        logger.info("Routing task to AI: %s", user_text)
        target_agent = await agent_router.route(user_text, context=router_ctx)
        if ws_manager.is_interrupted(client_id):
            logger.info("Turn interrupted after routing for %s", client_id)
            return
        router_time = time.time() - router_start
        logger.info(
            "⏱️ [LATENCY] Router (Agent selection: %s): %.3fs", target_agent, router_time
        )

        sentence_buffer = ""
        full_ai_text = ""
        first_audio_sent = [False]
        first_token_logged = [False]
        first_sentence_logged = [False]
        tts_total = [0.0]
        context = {
            "client_id": client_id,
            "session_id": session_id,
            "user_id": live["user_id"],
        }
        agent_stream_start = time.time()
        interrupted = False

        async for token in agent_router.stream_dispatch(target_agent, user_text, context):
            if ws_manager.is_interrupted(client_id):
                interrupted = True
                break

            if not first_token_logged[0] and token:
                first_token_logged[0] = True
                logger.info(
                    "⏱️ [LATENCY] Time-To-First-LLM-Token: %.3fs",
                    time.time() - agent_stream_start,
                )

            sentence_buffer += token
            full_ai_text += token

            while True:
                phrase, sentence_buffer = _pop_speakable(sentence_buffer)
                if not phrase:
                    break
                ok = await _speak_and_send(
                    client_id,
                    phrase,
                    pipeline_start=pipeline_start,
                    first_audio_sent=first_audio_sent,
                    tts_total=tts_total,
                    first_sentence_logged=first_sentence_logged,
                    agent_stream_start=agent_stream_start,
                )
                if not ok:
                    interrupted = True
                    break
            if interrupted:
                break

        if interrupted or ws_manager.is_interrupted(client_id):
            logger.info("Turn interrupted mid-stream for %s", client_id)
            if full_ai_text.strip():
                logger.info(
                    "BOT RESPONSE [interrupted, %d chars]: %s",
                    len(full_ai_text.strip()),
                    full_ai_text.strip().replace("\n", " "),
                )
                await session_manager.append_message(
                    client_id, "assistant", full_ai_text.strip() + " [interrupted]"
                )
            await ws_manager.send(
                client_id, {"type": "interrupted", "payload": "stopped"}
            )
            return

        remainder = sentence_buffer.strip()
        if remainder and not ws_manager.is_interrupted(client_id):
            await _speak_and_send(
                client_id,
                remainder,
                pipeline_start=pipeline_start,
                first_audio_sent=first_audio_sent,
                tts_total=tts_total,
                first_sentence_logged=first_sentence_logged,
                agent_stream_start=agent_stream_start,
            )

        if ws_manager.is_interrupted(client_id):
            await ws_manager.send(
                client_id, {"type": "interrupted", "payload": "stopped"}
            )
            return

        agent_total_time = time.time() - agent_stream_start
        save_start = time.time()
        await session_manager.append_message(client_id, "assistant", full_ai_text)
        logger.info(
            "⏱️ [LATENCY] Redis append_bot: %.3fs", time.time() - save_start
        )
        await ws_manager.send(
            client_id,
            {
                "type": "ai_text_complete",
                "payload": full_ai_text,
                "t_sent_ms": _now_ms(),
            },
        )

        total_pipeline_time = time.time() - pipeline_start
        reply = (full_ai_text or "").replace("\n", " ").strip()
        logger.info("BOT RESPONSE [%d chars]: %s", len(reply), reply)
        logger.info(
            "📊 [LATENCY SUMMARY] Total: %.3fs | STT: %.3fs | Router: %.3fs | "
            "Agent Stream: %.3fs | TTS Total: %.3fs | TTFA_hit: %s | agent=%s",
            total_pipeline_time,
            stt_time,
            router_time,
            agent_total_time,
            tts_total[0],
            first_audio_sent[0],
            target_agent,
        )
    except asyncio.CancelledError:
        logger.info("Turn task cancelled for %s", client_id)
        await ws_manager.send(client_id, {"type": "interrupted", "payload": "cancelled"})
        raise
    except Exception:
        logger.exception("Turn failed for client %s", client_id)
        await ws_manager.send(
            client_id, {"type": "error", "payload": "Turn processing failed"}
        )


@router.websocket("/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        from app.managers.session_manager import session_manager

        await session_manager.get_or_create(client_id)
    except Exception as e:
        logger.warning("Session hydrate skipped: %s", e)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "unknown")
            logger.debug("WS received from %s: %s", client_id, msg_type)

            if msg_type == "interrupt":
                ws_manager.request_interrupt(client_id)
                await ws_manager.send(
                    client_id, {"type": "interrupted", "payload": "ack"}
                )
                continue

            user_text = ""
            pipeline_start = time.time()
            stt_time = 0.0
            vad_silence_ms = data.get("vad_silence_ms")
            speech_ms = data.get("speech_ms")

            if msg_type == "audio":
                audio_b64 = data.get("data", "")
                if not audio_b64:
                    continue
                ws_manager.request_interrupt(client_id)
                await asyncio.sleep(0)

                audio_bytes = base64.b64decode(audio_b64)
                audio_format = (data.get("format") or "webm").lower()
                sample_rate = int(data.get("sample_rate") or 16000)
                logger.info(
                    "⏱️ [LATENCY] Audio recv: raw=%dB b64=%dB format=%s rate=%s",
                    len(audio_bytes),
                    len(audio_b64),
                    audio_format,
                    sample_rate,
                )
                stt_start = time.time()
                transcription = await voice_manager.transcribe(
                    audio_bytes,
                    filename="audio.pcm" if "pcm" in audio_format else "audio.webm",
                    audio_format=audio_format,
                )
                stt_time = time.time() - stt_start
                user_text = transcription.text.strip()
                logger.info(
                    "⏱️ [LATENCY] STT (Whisper): %.3fs | heard: %s",
                    stt_time,
                    user_text,
                )
                await ws_manager.send(
                    client_id,
                    {
                        "type": "transcription",
                        "payload": user_text,
                        "t_sent_ms": _now_ms(),
                    },
                )

            elif msg_type == "text":
                ws_manager.request_interrupt(client_id)
                await asyncio.sleep(0)
                user_text = data.get("data", "").strip()

            else:
                await ws_manager.send(client_id, {"type": "ack", "payload": data})
                continue

            if not user_text:
                continue

            # Check if this is a permission code response
            from app.core.permissions import verify_permission, has_pending
            if has_pending(client_id):
                perm_result = verify_permission(client_id, user_text)
                if perm_result is True:
                    await ws_manager.send(client_id, {"type": "permission_granted", "message": "Confirmed. Executing."})
                    continue
                elif perm_result is False:
                    await ws_manager.send(client_id, {"type": "permission_denied", "message": "Cancelled."})
                    continue
                # perm_result is None → not a permission response, proceed normally

            ws_manager.clear_interrupt(client_id)
            task = asyncio.create_task(
                _handle_turn(
                    client_id,
                    user_text,
                    stt_time,
                    pipeline_start,
                    vad_silence_ms=float(vad_silence_ms)
                    if vad_silence_ms is not None
                    else None,
                    speech_ms=float(speech_ms) if speech_ms is not None else None,
                )
            )
            ws_manager.set_turn_task(client_id, task)

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        from app.managers.session_manager import session_manager

        await session_manager.end_session(client_id, status="ENDED")
        logger.info("WS disconnected — session closed: %s", client_id)
    except Exception as e:
        logger.exception("WS error for client %s: %s", client_id, e)
        ws_manager.disconnect(client_id)
        from app.managers.session_manager import session_manager

        await session_manager.end_session(client_id, status="ABANDONED")
