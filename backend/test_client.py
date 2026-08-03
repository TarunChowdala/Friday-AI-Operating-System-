import asyncio
import websockets
import json
import base64

async def test_friday():
    uri = "ws://localhost:8000/ws/test_client_1"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            import sounddevice as sd
            import scipy.io.wavfile as wav
            import io
            import time

            # Audio recording parameters
            fs = 16000  # Whisper expects 16kHz
            duration = 5  # Record for 5 seconds

            print("\n🎙️  Get ready to speak!")
            input("Press Enter to start recording for 5 seconds...")
            
            print("🔴 Recording... Speak now!")
            myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()  # Wait until recording is finished
            print("✅ Recording complete!")

            # Convert to WAV bytes in memory
            wav_io = io.BytesIO()
            wav.write(wav_io, fs, myrecording)
            wav_bytes = wav_io.getvalue()
            
            # Base64 encode for WebSocket
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
            
            message = {
                "type": "audio",
                "data": audio_b64
            }
            
            print("\nSending audio up to FRIDAY...\n")
            await websocket.send(json.dumps(message))
            
            # Listen for responses
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                msg_type = data.get("type")
                payload = data.get("payload")
                
                if msg_type == "transcription":
                    print(f"🗣️  Whisper heard: '{payload}'")
                elif msg_type == "ai_text_chunk":
                    print(f"🧠 Ollama streaming text: '{payload}'")
                elif msg_type == "ai_audio_chunk":
                    audio_b64 = payload
                    print(f"🎵 TTS streamed audio chunk! (Base64 length: {len(audio_b64)})")
                elif msg_type == "ai_text_complete":
                    print("\n✅ Full Pipeline Test Complete!\n")
                    break
                    
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Make sure your FastAPI server is running! (uvicorn app.main:app)")

if __name__ == "__main__":
    asyncio.run(test_friday())
