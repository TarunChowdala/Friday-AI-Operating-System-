import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';

export function useFridayWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);

  const setAssistantState = useFridayStore((s) => s.setAssistantState);

  // Audio queue for smooth playback
  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlaying = useRef(false);

  // Mic & Silence Detection State
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const isMicEnabled = useRef<boolean>(false);

  const analyser = useRef<AnalyserNode | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSpeaking = useRef<boolean>(false);

  // Playback queue handler
  const playNextInQueue = useCallback(async () => {
    if (audioQueue.current.length === 0) {
      isPlaying.current = false;
      setAssistantState('listening'); // Instantly back to listening!

      // Re-arm mic recording after AI finishes speaking
      if (isMicEnabled.current) {
        setTimeout(() => {
          if (!isPlaying.current && isMicEnabled.current) {
            startListening();
          }
        }, 200);
      }
      return;
    }

    isPlaying.current = true;
    setAssistantState('speaking');

    const buffer = audioQueue.current.shift()!;
    const source = audioContext.current!.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.current!.destination);
    source.onended = () => playNextInQueue();
    source.start(0);
  }, [setAssistantState]);

  // Connect WebSocket & AudioContext
  useEffect(() => {
    audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    const clientId = 'browser_client_' + Math.floor(Math.random() * 1000);
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      const socket = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
      ws.current = socket;

      socket.onopen = () => console.log('✅ Connected to FRIDAY WebSocket');

      socket.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        const { type: msgType, payload } = data;

        switch (msgType) {
          case 'transcription':
            setAssistantState('thinking');
            break;

          case 'ai_audio_chunk':
            try {
              const binaryString = window.atob(payload);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              const audioBuf = await audioContext.current!.decodeAudioData(bytes.buffer);
              audioQueue.current.push(audioBuf);

              if (!isPlaying.current) {
                playNextInQueue();
              }
            } catch (err) {
              console.error("Audio decode error", err);
            }
            break;
        }
      };

      socket.onerror = (err) => console.error('WebSocket Error:', err);
      socket.onclose = () => {
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws.current) ws.current.close();
      if (audioContext.current) audioContext.current.close();
    };
  }, [playNextInQueue, setAssistantState]);

  // Microphone recording with intelligent 900ms silence detection
  const startListening = useCallback(async () => {
    try {
      if (mediaRecorder.current && mediaRecorder.current.state === 'recording') return;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Setup Web Audio VAD Analyser
      if (!audioContext.current) {
        audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const sourceNode = audioContext.current.createMediaStreamSource(stream);
      const analyserNode = audioContext.current.createAnalyser();
      analyserNode.fftSize = 256;
      sourceNode.connect(analyserNode);
      analyser.current = analyserNode;

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorder.current = recorder;
      audioChunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });

        // Only submit if user actually spoke (audio size > 2500 bytes)
        if (audioBlob.size > 2500 && ws.current && ws.current.readyState === WebSocket.OPEN) {
          const buffer = await audioBlob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = '';
          bytes.forEach((b) => binary += String.fromCharCode(b));
          const base64 = window.btoa(binary);

          setAssistantState('thinking');
          ws.current.send(JSON.stringify({ type: 'audio', data: base64 }));
        } else {
          // Re-arm listening if slice was silent noise
          if (isMicEnabled.current && !isPlaying.current) {
            startListening();
          }
        }
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start(100);
      isMicEnabled.current = true;
      setAssistantState('listening');
      useFridayStore.setState({ isMicActive: true });

      // Check audio volume every 50ms for 900ms silence window
      const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
      isSpeaking.current = false;

      const vadLoop = setInterval(() => {
        if (isPlaying.current) {
          clearInterval(vadLoop);
          return;
        }

        analyserNode.getByteFrequencyData(dataArray);
        let maxVolume = 0;
        for (let i = 0; i < dataArray.length; i++) {
          if (dataArray[i] > maxVolume) maxVolume = dataArray[i];
        }

        // Voice detection threshold
        if (maxVolume > 20) {
          if (!isSpeaking.current) {
            console.log("🗣️ Speaking...");
            isSpeaking.current = true;
          }
          if (silenceTimer.current) clearTimeout(silenceTimer.current);
        } else {
          // If user started speaking and then stopped for 900ms -> SUBMIT!
          if (isSpeaking.current && !silenceTimer.current) {
            silenceTimer.current = setTimeout(() => {
              console.log("🔇 Sentence finished (900ms silence). Answering...");
              clearInterval(vadLoop);
              isSpeaking.current = false;
              silenceTimer.current = null;
              if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
                mediaRecorder.current.stop();
              }
            }, 900); // 900ms gives plenty of time to pause mid-sentence naturally!
          }
        }
      }, 50);

    } catch (err) {
      console.error("Mic access error:", err);
      setAssistantState('idle');
      useFridayStore.setState({ isMicActive: false });
    }
  }, [setAssistantState]);

  // Toggle Mic Button handler (Mute / Unmute)
  const toggleMic = () => {
    if (isMicEnabled.current) {
      isMicEnabled.current = false;
      if (silenceTimer.current) clearTimeout(silenceTimer.current);
      if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
        mediaRecorder.current.stop();
      }
      useFridayStore.setState({ isMicActive: false });
      setAssistantState('idle');
    } else {
      isMicEnabled.current = true;
      startListening();
    }
  };

  return {
    toggleMic,
    isMicActive: isMicEnabled.current
  };
}
