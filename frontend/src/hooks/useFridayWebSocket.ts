import { useEffect, useRef, useState, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';

export function useFridayWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);

  // Track the conversation locally
  const [transcription, setTranscription] = useState<string>('');
  const [aiResponse, setAiResponse] = useState<string>('');

  const setAssistantState = useFridayStore((s) => s.setAssistantState);

  // Queue to play audio chunks sequentially
  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlaying = useRef(false);

  const playNextInQueue = useCallback(async () => {
    if (audioQueue.current.length === 0) {
      isPlaying.current = false;
      setAssistantState('idle'); // Finished speaking
      return;
    }

    isPlaying.current = true;
    setAssistantState('speaking');

    const buffer = audioQueue.current.shift()!;
    const source = audioContext.current!.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.current!.destination);

    source.onended = () => {
      playNextInQueue();
    };

    source.start(0);
  }, [setAssistantState]);

  useEffect(() => {
    // Initialize Web Audio API
    audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();

    const clientId = 'browser_client_' + Math.floor(Math.random() * 1000);
    const socket = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
    ws.current = socket;

    socket.onopen = () => {
      console.log('✅ Connected to FRIDAY WebSocket');
    };

    socket.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      const msgType = data.type;
      const payload = data.payload;

      switch (msgType) {
        case 'transcription':
          setTranscription(payload);
          setAiResponse('');
          setAssistantState('thinking');
          break;

        case 'ai_text_chunk':
          setAiResponse((prev) => prev + (prev ? ' ' : '') + payload);
          break;

        case 'ai_audio_chunk':
          // Decode Base64 to ArrayBuffer
          const binaryString = window.atob(payload);
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }

          try {
            // Decode the audio data (WAV)
            const audioBuf = await audioContext.current!.decodeAudioData(bytes.buffer);
            audioQueue.current.push(audioBuf);

            // If not already playing, start!
            if (!isPlaying.current) {
              playNextInQueue();
            }
          } catch (err) {
            console.error("Failed to decode audio chunk", err);
          }
          break;

        case 'ai_text_complete':
          console.log('Full AI Response Generated');
          break;
      }
    };

    socket.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };

    socket.onclose = () => {
      console.log('WebSocket Disconnected');
    };

    return () => {
      socket.close();
      if (audioContext.current) {
        audioContext.current.close();
      }
    };
  }, [playNextInQueue, setAssistantState]);

  // Method to send a raw text message
  const sendText = (text: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setTranscription(text);
      setAiResponse('');
      setAssistantState('thinking');

      ws.current.send(
        JSON.stringify({
          type: 'text',
          data: text,
        })
      );
    }
  };

  // Microphone recording
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorder.current = recorder;
      audioChunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });
        const buffer = await audioBlob.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = '';
        bytes.forEach((b) => binary += String.fromCharCode(b));
        const base64 = window.btoa(binary);

        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          setAiResponse('');
          setAssistantState('thinking');
          ws.current.send(JSON.stringify({ type: 'audio', data: base64 }));
        }

        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setAssistantState('listening');
    } catch (err) {
      console.error("Mic error:", err);
      setAssistantState('idle');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
      mediaRecorder.current.stop();
    }
  };

  return {
    transcription,
    aiResponse,
    sendText,
    startRecording,
    stopRecording
  };
}
