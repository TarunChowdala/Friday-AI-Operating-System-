import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';

/**
 * Flow (header mic):
 *
 * 1. Click mic ON  → state: listening  (recorder + VAD start)
 * 2. You talk      → VAD marks speech
 * 3. You stop      → 900ms silence → audio sent to backend
 * 4. Backend STT   → state: thinking
 * 5. TTS chunks    → state: speaking  (sphere turns yellow)
 * 6. Playback done → state: listening again (mic still on)
 *
 * Click mic OFF anytime → state: idle, recorder killed
 */
export function useFridayWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);

  const setAssistantState = useFridayStore((s) => s.setAssistantState);

  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlaying = useRef(false);

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const isMicEnabled = useRef(false);
  const mediaStream = useRef<MediaStream | null>(null);

  const analyser = useRef<AnalyserNode | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const vadInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const isSpeaking = useRef(false);
  const startListeningRef = useRef<() => Promise<void>>(async () => {});

  const clearVad = () => {
    if (vadInterval.current) {
      clearInterval(vadInterval.current);
      vadInterval.current = null;
    }
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current);
      silenceTimer.current = null;
    }
  };

  const stopTracks = () => {
    mediaStream.current?.getTracks().forEach((t) => t.stop());
    mediaStream.current = null;
  };

  const playNextInQueue = useCallback(async () => {
    if (audioQueue.current.length === 0) {
      isPlaying.current = false;
      if (isMicEnabled.current) {
        setAssistantState('listening');
        setTimeout(() => {
          if (!isPlaying.current && isMicEnabled.current) {
            startListeningRef.current();
          }
        }, 250);
      } else {
        setAssistantState('idle');
      }
      return;
    }

    isPlaying.current = true;
    setAssistantState('speaking');

    // Resume context — browsers suspend until a user gesture / resume
    if (audioContext.current?.state === 'suspended') {
      await audioContext.current.resume();
    }

    const buffer = audioQueue.current.shift()!;
    const source = audioContext.current!.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.current!.destination);
    source.onended = () => playNextInQueue();
    source.start(0);
  }, [setAssistantState]);

  useEffect(() => {
    audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    const clientId = 'browser_client_' + Math.floor(Math.random() * 1000);
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let closed = false;

    const connect = () => {
      if (closed) return;
      const socket = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
      ws.current = socket;

      socket.onopen = () => {
        console.log('✅ Connected to FRIDAY WebSocket');
        useFridayStore.setState({ isConnected: true });
      };

      socket.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        const { type: msgType, payload } = data;

        switch (msgType) {
          case 'transcription':
            console.log('📝 Transcription:', payload);
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
              if (!isPlaying.current) playNextInQueue();
            } catch (err) {
              console.error('Audio decode error', err);
            }
            break;

          case 'error':
            console.error('WS error payload:', payload);
            setAssistantState(isMicEnabled.current ? 'listening' : 'idle');
            break;
        }
      };

      socket.onerror = (err) => console.error('WebSocket Error:', err);
      socket.onclose = () => {
        useFridayStore.setState({ isConnected: false });
        if (!closed) reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      closed = true;
      clearTimeout(reconnectTimeout!);
      clearVad();
      stopTracks();
      if (ws.current) ws.current.close();
      if (audioContext.current) audioContext.current.close();
    };
  }, [playNextInQueue, setAssistantState]);

  const startListening = useCallback(async () => {
    try {
      if (mediaRecorder.current && mediaRecorder.current.state === 'recording') return;
      if (isPlaying.current) return;

      clearVad();

      if (audioContext.current?.state === 'suspended') {
        await audioContext.current.resume();
      }
      if (!audioContext.current) {
        audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStream.current = stream;

      const sourceNode = audioContext.current.createMediaStreamSource(stream);
      const analyserNode = audioContext.current.createAnalyser();
      analyserNode.fftSize = 512;
      analyserNode.smoothingTimeConstant = 0.5;
      sourceNode.connect(analyserNode);
      analyser.current = analyserNode;

      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      mediaRecorder.current = recorder;
      audioChunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };

      recorder.onstop = async () => {
        clearVad();
        const audioBlob = new Blob(audioChunks.current, { type: mime });
        audioChunks.current = [];
        stopTracks();
        mediaRecorder.current = null;

        // Mic was turned off — don't submit / re-arm
        if (!isMicEnabled.current || isPlaying.current) return;

        console.log(`🎙️ Slice size: ${audioBlob.size} bytes`);

        if (audioBlob.size > 1500 && ws.current?.readyState === WebSocket.OPEN) {
          const buffer = await audioBlob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = '';
          for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
          const base64 = window.btoa(binary);

          setAssistantState('thinking');
          console.log('📤 Sending audio to FRIDAY...');
          ws.current.send(JSON.stringify({ type: 'audio', data: base64 }));
        } else {
          console.log('🔇 Slice too small / WS closed — re-arming listen');
          if (isMicEnabled.current && !isPlaying.current) {
            startListeningRef.current();
          }
        }
      };

      recorder.start(100);
      isMicEnabled.current = true;
      isSpeaking.current = false;
      setAssistantState('listening');
      useFridayStore.setState({ isMicActive: true });
      console.log('🎧 Listening...');

      const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
      const SPEECH_THRESHOLD = 12; // avg frequency energy
      const SILENCE_MS = 900;
      const MAX_UTTERANCE_MS = 12000;
      const startedAt = Date.now();

      vadInterval.current = setInterval(() => {
        if (isPlaying.current || !mediaRecorder.current || mediaRecorder.current.state !== 'recording') {
          clearVad();
          return;
        }

        // Hard cap utterance length
        if (Date.now() - startedAt > MAX_UTTERANCE_MS && isSpeaking.current) {
          console.log('⏱️ Max utterance — submitting');
          clearVad();
          mediaRecorder.current.stop();
          return;
        }

        analyserNode.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;

        if (avg > SPEECH_THRESHOLD) {
          if (!isSpeaking.current) {
            console.log('🗣️ Speech detected');
            isSpeaking.current = true;
          }
          if (silenceTimer.current) {
            clearTimeout(silenceTimer.current);
            silenceTimer.current = null;
          }
        } else if (isSpeaking.current && !silenceTimer.current) {
          silenceTimer.current = setTimeout(() => {
            console.log('🔇 Silence 900ms — submitting');
            silenceTimer.current = null;
            isSpeaking.current = false;
            clearVad();
            if (mediaRecorder.current?.state === 'recording') {
              mediaRecorder.current.stop();
            }
          }, SILENCE_MS);
        }
      }, 50);
    } catch (err) {
      console.error('Mic access error:', err);
      isMicEnabled.current = false;
      setAssistantState('idle');
      useFridayStore.setState({ isMicActive: false });
    }
  }, [setAssistantState]);

  startListeningRef.current = startListening;

  const toggleMic = useCallback(async () => {
    if (audioContext.current?.state === 'suspended') {
      await audioContext.current.resume();
    }

    if (isMicEnabled.current) {
      // Turn OFF
      console.log('🎤 Mic OFF');
      isMicEnabled.current = false;
      clearVad();
      if (mediaRecorder.current?.state === 'recording') {
        mediaRecorder.current.stop();
      } else {
        stopTracks();
      }
      useFridayStore.setState({ isMicActive: false });
      setAssistantState('idle');
    } else {
      // Turn ON
      console.log('🎤 Mic ON');
      isMicEnabled.current = true;
      await startListening();
    }
  }, [setAssistantState, startListening]);

  return { toggleMic };
}
