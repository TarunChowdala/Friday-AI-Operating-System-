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
                if not audio_b64:
                    continue
                audio_bytes = base64.b64decode(audio_b64)

                # 2. Transcribe (Speech-to-Text)
                logger.info("Transcribing incoming audio...")
                transcription = await voice_manager.transcribe(audio_bytes)
                user_text = transcription.text.strip()
                
                # Send what FRIDAY heard back to the frontend UI
                await ws_manager.send(client_id, {"type": "transcription", "payload": user_text})

            elif msg_type == "text":
                # Bypass STT for direct text input
                user_text = data.get("data", "").strip()

            else:
                # Handle generic pings/acks
                await ws_manager.send(client_id, {"type": "ack", "payload": data})
                continue

            # If Whisper heard nothing (like from fake test bytes) or empty text was sent, skip the LLM.
            if not user_text:
                continue

            # 3. Route Task
            import time
            start_time = time.time()
            logger.info("Routing task to AI: %s", user_text)
            
            target_agent = await agent_router.route(user_text)
            
            # 4. Stream Process (LLM -> TTS -> Client)
            sentence_buffer = ""
            full_ai_text = ""
            logger.info("Streaming response from %s...", target_agent)
            
            async for token in agent_router.stream_dispatch(target_agent, user_text, {}):
                sentence_buffer += token
                full_ai_text += token
                
                # Check for sentence boundaries
                if any(punc in token for punc in [".", "!", "?", "\n"]):
                    text_to_speak = sentence_buffer.strip()
                    if text_to_speak:
                        # Send text chunk to UI
                        await ws_manager.send(client_id, {"type": "ai_text_chunk", "payload": text_to_speak})
                        
                        # Synthesize this sentence
                        tts_req = TTSRequest(text=text_to_speak, voice_id="default")
                        tts_res = await voice_manager.synthesize(tts_req)
                        
                        if tts_res.audio_data:
                            ai_audio_b64 = base64.b64encode(tts_res.audio_data).decode("utf-8")
                            await ws_manager.send(client_id, {"type": "ai_audio_chunk", "payload": ai_audio_b64})
                            
                    sentence_buffer = ""
                    
            # Catch any remaining text in the buffer
            text_to_speak = sentence_buffer.strip()
            if text_to_speak:
                await ws_manager.send(client_id, {"type": "ai_text_chunk", "payload": text_to_speak})
                
                tts_req = TTSRequest(text=text_to_speak, voice_id="default")
                tts_res = await voice_manager.synthesize(tts_req)
                if tts_res.audio_data:
                    ai_audio_b64 = base64.b64encode(tts_res.audio_data).decode("utf-8")
                    await ws_manager.send(client_id, {"type": "ai_audio_chunk", "payload": ai_audio_b64})

            # Send final completion flag
            await ws_manager.send(client_id, {"type": "ai_text_complete", "payload": full_ai_text})
            
            total_time = time.time() - start_time
            logger.info("Total stream processing took %.2f seconds", total_time)

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info("WS disconnected: %s", client_id)
    except Exception as e:
        logger.error("WS error: %s", e)
        ws_manager.disconnect(client_id)
