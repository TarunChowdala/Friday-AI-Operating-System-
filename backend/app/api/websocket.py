"""WebSocket API routes."""
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logger import get_logger
from app.websocket.connection_manager import ConnectionManager
from app.managers.voice_manager import VoiceManager
from app.agents.router import AgentRouter
from app.models.voice import TTSRequest

router = APIRouter()
logger = get_logger(__name__)

# Initialize singletons for the WebSocket lifecycle
ws_manager = ConnectionManager()
voice_manager = VoiceManager()
agent_router = AgentRouter()


@router.websocket("/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:



        while True:
            data = await websocket.receive_json()

            msg_type = data.get("type", "unknown")
            logger.debug("WS received from %s: %s", client_id, msg_type)

            user_text = ""

            if msg_type == "audio":
                # 1. Decode Frontend Audio (Base64)
                audio_b64 = data.get("data", "")
            # Track pipeline latency breakdown
            import time
            pipeline_start = time.time()
            stt_time = 0.0

            if msg_type == "audio":
                # 1. Decode Frontend Audio (Base64)
                audio_b64 = data.get("data", "")
                if not audio_b64:
                    continue
                audio_bytes = base64.b64decode(audio_b64)

                # 2. Transcribe (Speech-to-Text)
                stt_start = time.time()
                transcription = await voice_manager.transcribe(audio_bytes)
                stt_time = time.time() - stt_start
                user_text = transcription.text.strip()
                logger.info(f"⏱️ [LATENCY] STT (Whisper): {stt_time:.3f}s")
                
                # Send what FRIDAY heard back to the frontend UI
                await ws_manager.send(client_id, {"type": "transcription", "payload": user_text})

            elif msg_type == "text":
                # Bypass STT for direct text input
                user_text = data.get("data", "").strip()

            else:
                # Handle generic pings/acks
                await ws_manager.send(client_id, {"type": "ack", "payload": data})
                continue

            # If Whisper heard nothing, skip
            if not user_text:
                continue

            # 3. Add to Conversation Memory
            from app.memory.conversation import conversation_memory
            conversation_memory.add_human_message(client_id, user_text)

            # 4. Route Task
            router_start = time.time()
            logger.info("Routing task to AI: %s", user_text)
            
            target_agent = await agent_router.route(user_text)
            router_time = time.time() - router_start
            logger.info(f"⏱️ [LATENCY] Router (Agent selection: {target_agent}): {router_time:.3f}s")
            
            # 5. Stream Process (LLM -> TTS -> Client)
            sentence_buffer = ""
            full_ai_text = ""
            first_audio_sent = False
            ttfa_time = 0.0
            tts_total_time = 0.0
            
            # Pass client_id so the agent can fetch conversation history
            context = {"client_id": client_id}
            agent_stream_start = time.time()
            
            async for token in agent_router.stream_dispatch(target_agent, user_text, context):
                sentence_buffer += token
                full_ai_text += token
                
                # Check for sentence boundaries
                if any(punc in token for punc in [".", "!", "?", "\n"]):
                    text_to_speak = sentence_buffer.strip()
                    if text_to_speak:
                        await ws_manager.send(client_id, {"type": "ai_text_chunk", "payload": text_to_speak})
                        
                        tts_start = time.time()
                        tts_req = TTSRequest(text=text_to_speak, voice_id="default")
                        tts_res = await voice_manager.synthesize(tts_req)
                        tts_elapsed = time.time() - tts_start
                        tts_total_time += tts_elapsed
                        
                        if tts_res.audio_data:
                            if not first_audio_sent:
                                first_audio_sent = True
                                ttfa_time = time.time() - pipeline_start
                                logger.info(f"⚡ [LATENCY] Time-To-First-Audio (TTFA): {ttfa_time:.3f}s")
                                
                            ai_audio_b64 = base64.b64encode(tts_res.audio_data).decode("utf-8")
                            await ws_manager.send(client_id, {"type": "ai_audio_chunk", "payload": ai_audio_b64})
                            
                    sentence_buffer = ""
                    
            # Catch remaining text
            text_to_speak = sentence_buffer.strip()
            if text_to_speak:
                await ws_manager.send(client_id, {"type": "ai_text_chunk", "payload": text_to_speak})
                tts_start = time.time()
                tts_req = TTSRequest(text=text_to_speak, voice_id="default")
                tts_res = await voice_manager.synthesize(tts_req)
                tts_total_time += (time.time() - tts_start)
                if tts_res.audio_data:
                    ai_audio_b64 = base64.b64encode(tts_res.audio_data).decode("utf-8")
                    await ws_manager.send(client_id, {"type": "ai_audio_chunk", "payload": ai_audio_b64})

            agent_total_time = time.time() - agent_stream_start

            # Save the final AI response to memory
            conversation_memory.add_ai_message(client_id, full_ai_text)

            # Send final completion flag
            await ws_manager.send(client_id, {"type": "ai_text_complete", "payload": full_ai_text})
            
            total_pipeline_time = time.time() - pipeline_start
            logger.info(
                f"📊 [LATENCY SUMMARY] Total: {total_pipeline_time:.3f}s | "
                f"STT: {stt_time:.3f}s | Router: {router_time:.3f}s | "
                f"Agent Stream: {agent_total_time:.3f}s | TTS Total: {tts_total_time:.3f}s"
            )


    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info("WS disconnected cleanly: %s", client_id)
    except Exception as e:
        logger.exception("WS error for client %s: %s", client_id, e)
        ws_manager.disconnect(client_id)

