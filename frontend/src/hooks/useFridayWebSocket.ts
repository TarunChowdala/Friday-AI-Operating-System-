import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';
import { MicVAD } from "@ricky0123/vad-web";

/** Tunable VAD / endpointing (energy VAD — not Silero). */
export const VAD_CONFIG = {
  /** Fallback if noise floor isn't ready yet. Speech-band energy, not all FFT bins. */
  SPEECH_THRESHOLD: 45,
  SILENCE_MS: 650,
  MAX_UTTERANCE_MS: 12000,
  VAD_POLL_MS: 50,
  NOISE_CALIBRATE_MS: 400,
  SPEECH_MARGIN: 25,
  SILENCE_MARGIN: 7,
} as const;

export const PCM_SAMPLE_RATE = 16000;

function floatToPcm16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function int16ToBase64(samples: Int16Array): string {
  const bytes = new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return window.btoa(binary);
}

function pcm16ToAudioBuffer(
  ctx: AudioContext,
  payloadB64: string,
  sampleRate: number
): AudioBuffer {
  const binary = window.atob(payloadB64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const n = Math.floor(bytes.byteLength / 2);
  const buf = ctx.createBuffer(1, Math.max(n, 1), sampleRate);
  const ch = buf.getChannelData(0);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let i = 0; i < n; i++) ch[i] = view.getInt16(i * 2, true) / 32768;
  return buf;
}

/**
 * Flow (header mic):
 *
 * 1. Click mic ON  → state: listening  (recorder + VAD start)
 * 2. You talk      → VAD marks speech
 * 3. You stop      → SILENCE_MS → audio sent to backend
 * 4. Backend STT   → state: thinking
 * 5. TTS chunks    → state: speaking
 * 6. Playback done → state: listening again (mic still on)
 *
 * Barge-in: speak while JARVIS talks → stop TTS, interrupt backend, listen.
 */
export function useFridayWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);

  const setAssistantState = useFridayStore((s) => s.setAssistantState);

  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlaying = useRef(false);
  const currentSource = useRef<AudioBufferSourceNode | null>(null);
  const ignoreTts = useRef(false);
  /** True from user submit until ai_text_complete / interrupt — blocks premature mic re-arm between TTS chunks */
  const responseActive = useRef(false);

  const isCapturing = useRef(false);
  const isMicEnabled = useRef(false);
  const mediaStream = useRef<MediaStream | null>(null);
  const myvad = useRef<any>(null);

  const bargeInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const bargeGraceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakingStartedAt = useRef(0);
  const isSpeaking = useRef(false);
  const startListeningRef = useRef<() => Promise<void>>(async () => {});
  const interruptRef = useRef<() => void>(() => {});
  const turnClock = useRef<{
    speechAt: number | null;
    silenceAt: number | null;
    sendAt: number | null;
    firstText: boolean;
    firstAudio: boolean;
    firstPlayback: boolean;
  }>({
    speechAt: null,
    silenceAt: null,
    sendAt: null,
    firstText: false,
    firstAudio: false,
    firstPlayback: false,
  });

  const feLatency = (label: string, extra = '') => {
    const t = turnClock.current;
    const now = Date.now();
    const fromSend = t.sendAt != null ? `${now - t.sendAt}ms from WS send` : 'no send yet';
    const net = extra ? ` | ${extra}` : '';
    console.log(`⏱️ [FE LATENCY] ${label} | ${fromSend}${net}`);
  };

  const clearVad = () => {
    if (myvad.current) {
      myvad.current.pause();
    }
  };

  const clearBargeIn = () => {
    if (bargeInterval.current) {
      clearInterval(bargeInterval.current);
      bargeInterval.current = null;
    }
    if (bargeGraceTimer.current) {
      clearTimeout(bargeGraceTimer.current);
      bargeGraceTimer.current = null;
    }
  };

  const stopTracks = () => {
    mediaStream.current?.getTracks().forEach((t) => t.stop());
    mediaStream.current = null;
  };

  const stopPlayback = useCallback(() => {
    try {
      currentSource.current?.stop();
    } catch {
      /* already stopped */
    }
    currentSource.current = null;
    audioQueue.current = [];
    isPlaying.current = false;
  }, []);

  const sendInterrupt = useCallback(() => {
    ignoreTts.current = true;
    responseActive.current = false;
    stopPlayback();
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'interrupt' }));
      console.log('⛔ Sent interrupt to FRIDAY');
    }
    setAssistantState(isMicEnabled.current ? 'listening' : 'idle');
  }, [setAssistantState, stopPlayback]);

  interruptRef.current = sendInterrupt;

  const playNextInQueue = useCallback(async () => {
    if (ignoreTts.current) {
      audioQueue.current = [];
      isPlaying.current = false;
      return;
    }

    if (audioQueue.current.length === 0) {
      isPlaying.current = false;
      clearBargeIn();
      if (turnClock.current.sendAt) {
        feLatency('playback queue empty');
      }
      // Turn audio drained — clear sticky response flag so mic can re-arm
      if (!responseActive.current || ignoreTts.current) {
        /* ok */
      }
      // Only re-arm mic when the backend turn is fully done — NOT between TTS sentences
      if (isMicEnabled.current && !responseActive.current) {
        setAssistantState('listening');
        setTimeout(() => {
          if (!isPlaying.current && !responseActive.current && isMicEnabled.current) {
            startListeningRef.current();
          }
        }, 200);
      } else if (!isMicEnabled.current) {
        setAssistantState('idle');
      } else {
        setAssistantState('speaking'); // still expecting more audio
      }
      return;
    }

    const wasIdle = !isPlaying.current;
    if (wasIdle) {
      speakingStartedAt.current = Date.now();
    }
    isPlaying.current = true;
    setAssistantState('speaking');

    if (audioContext.current?.state === 'suspended') {
      await audioContext.current.resume();
    }

    const buffer = audioQueue.current.shift()!;
    if (wasIdle && !turnClock.current.firstPlayback) {
      turnClock.current.firstPlayback = true;
      feLatency(
        'first playback start (heard)',
        `buffer=${buffer.duration.toFixed(2)}s queue_left=${audioQueue.current.length}`
      );
    }
    const source = audioContext.current!.createBufferSource();
    currentSource.current = source;
    source.buffer = buffer;
    source.connect(audioContext.current!.destination);
    source.onended = () => {
      if (currentSource.current === source) {
        currentSource.current = null;
      }
      playNextInQueue();
    };
    console.log(
      `🔊 [LATENCY] Browser playback start | buffer=${buffer.duration.toFixed(2)}s | queue_left=${audioQueue.current.length}`
    );
    source.start(0);
  }, [setAssistantState]);

  /** Barge-in: short echo grace, then stop on sustained user speech. */
  const startBargeInMonitor = useCallback(async () => {
    clearBargeIn();
    if (!isMicEnabled.current) return;

    const BARGE_GRACE_MS = 700; // ignore her own voice echo at start of TTS
    const BARGE_THRESHOLD = 45;
    const REQUIRED_HITS = 8; // ~400ms sustained user speech before stop (50ms ticks)

    bargeGraceTimer.current = setTimeout(async () => {
      bargeGraceTimer.current = null;
      if (!isPlaying.current || !isMicEnabled.current) return;

      try {
        if (audioContext.current?.state === 'suspended') {
          await audioContext.current.resume();
        }
        if (!audioContext.current) {
          audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }

        let stream = mediaStream.current;
        if (!stream || stream.getAudioTracks().every((t) => t.readyState !== 'live')) {
          stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });
          mediaStream.current = stream;
        }

        const sourceNode = audioContext.current.createMediaStreamSource(stream);
        const analyserNode = audioContext.current.createAnalyser();
        analyserNode.fftSize = 512;
        analyserNode.smoothingTimeConstant = 0.5;
        sourceNode.connect(analyserNode);

        const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
        let hits = 0;

        bargeInterval.current = setInterval(() => {
          if (!isPlaying.current || !isMicEnabled.current) {
            clearBargeIn();
            return;
          }
          if (Date.now() - speakingStartedAt.current < BARGE_GRACE_MS) {
            hits = 0;
            return;
          }

          analyserNode.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
          const avg = sum / dataArray.length;

          if (avg > BARGE_THRESHOLD) {
            hits += 1;
            if (hits >= REQUIRED_HITS) {
              console.log('🗣️ Barge-in (avg=', avg.toFixed(1), ')');
              clearBargeIn();
              interruptRef.current();
              setTimeout(() => {
                if (isMicEnabled.current && !isPlaying.current && !responseActive.current) {
                  startListeningRef.current();
                }
              }, 80);
            }
          } else {
            hits = 0;
          }
        }, 50);
      } catch (err) {
        console.error('Barge-in monitor failed:', err);
      }
    }, BARGE_GRACE_MS);
  }, []);

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
          case 'transcription': {
            const net = typeof data.t_sent_ms === 'number' ? `net=${Date.now() - data.t_sent_ms}ms` : '';
            feLatency('transcription', `${net} text="${payload}"`);
            console.log('📝 Transcription:', payload);
            ignoreTts.current = false;
            responseActive.current = true;
            setAssistantState('thinking');
            break;
          }

          case 'interrupted':
            console.log('⛔ Backend interrupted:', payload);
            ignoreTts.current = true;
            responseActive.current = false;
            stopPlayback();
            break;

          case 'ai_text_chunk': {
            const net = typeof data.t_sent_ms === 'number' ? `net=${Date.now() - data.t_sent_ms}ms` : '';
            if (!turnClock.current.firstText) {
              turnClock.current.firstText = true;
              feLatency('first text chunk', `${net} text="${payload}"`);
            } else {
              feLatency('text chunk', `${net} text="${payload}"`);
            }
            break;
          }

          case 'ai_audio_chunk':
            if (ignoreTts.current) {
              console.log('⏭️ Dropping TTS chunk (interrupted)');
              break;
            }
            responseActive.current = true;
            try {
              const decodeT0 = Date.now();
              const net = typeof data.t_sent_ms === 'number' ? Date.now() - data.t_sent_ms : null;
              const fmt = (data.format as string) || 'mp3';
              const rate = Number(data.sample_rate) || PCM_SAMPLE_RATE;
              let audioBuf: AudioBuffer;
              if (fmt === 'pcm_s16le' || fmt === 'pcm') {
                audioBuf = pcm16ToAudioBuffer(audioContext.current!, payload, rate);
              } else {
                const binaryString = window.atob(payload);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                  bytes[i] = binaryString.charCodeAt(i);
                }
                audioBuf = await audioContext.current!.decodeAudioData(bytes.buffer);
              }
              const decodeMs = Date.now() - decodeT0;
              if (!turnClock.current.firstAudio) {
                turnClock.current.firstAudio = true;
                feLatency(
                  'first audio chunk',
                  `fmt=${fmt} decode=${decodeMs}ms net=${net ?? '?'}ms bytes=${payload.length} dur=${audioBuf.duration.toFixed(2)}s`
                );
              } else {
                feLatency(
                  'audio chunk',
                  `fmt=${fmt} decode=${decodeMs}ms net=${net ?? '?'}ms dur=${audioBuf.duration.toFixed(2)}s`
                );
              }
              if (ignoreTts.current) break;
              audioQueue.current.push(audioBuf);
              const wasIdle = !isPlaying.current;
              if (wasIdle) {
                playNextInQueue();
                startBargeInMonitor();
              }
            } catch (err) {
              console.error('Audio decode error', err);
            }
            break;

          case 'ai_text_complete': {
            const net = typeof data.t_sent_ms === 'number' ? `net=${Date.now() - data.t_sent_ms}ms` : '';
            feLatency('ai_text_complete', `${net} reply="${payload}"`);
            console.log('BOT RESPONSE:', payload);
            ignoreTts.current = false;
            responseActive.current = false;
            // Turn finished — re-arm mic if playback already drained
            if (isMicEnabled.current && !isPlaying.current && audioQueue.current.length === 0) {
              setAssistantState('listening');
              setTimeout(() => {
                if (!isPlaying.current && !responseActive.current && isMicEnabled.current) {
                  startListeningRef.current();
                }
              }, 200);
            }
            break;
          }

          case 'error':
            console.error('WS error payload:', payload);
            responseActive.current = false;
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
      clearBargeIn();
      stopTracks();
      stopPlayback();
      if (ws.current) ws.current.close();
      if (audioContext.current) audioContext.current.close();
    };
  }, [playNextInQueue, setAssistantState, startBargeInMonitor, stopPlayback]);

  const startListening = useCallback(async () => {
    try {
      if (isCapturing.current) return;
      if (responseActive.current && !isPlaying.current && audioQueue.current.length === 0) {
        responseActive.current = false;
      }

      if (isPlaying.current || audioQueue.current.length > 0) {
        sendInterrupt();
      }

      clearVad();
      clearBargeIn();

      if (audioContext.current?.state === 'suspended') {
        await audioContext.current.resume();
      }
      if (!audioContext.current) {
        audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      mediaStream.current = stream;

      isCapturing.current = true;
      isMicEnabled.current = true;
      isSpeaking.current = false;
      setAssistantState('listening');
      useFridayStore.setState({ isMicActive: true });
      console.log('🎧 Listening (Silero AI VAD)...');

      myvad.current = await MicVAD.new({
        getStream: async () => stream,
        positiveSpeechThreshold: 0.5,
        redemptionMs: 650,
        baseAssetPath: "/",
        onnxWASMBasePath: "/",
        model: "legacy",
        onSpeechStart: () => {
          console.log("🗣️ Speech started (Silero)");
          isSpeaking.current = true;
        },
        onSpeechEnd: (audio) => {
          console.log("🔇 Speech ended (Silero). Processing chunk...");
          isSpeaking.current = false;
          
          const pcm16 = floatToPcm16(audio);
          const bytes = pcm16.byteLength;
          console.log(`🎙️ PCM slice: ${bytes} bytes`);

          if (bytes > 3200 && ws.current?.readyState === WebSocket.OPEN) {
            ignoreTts.current = false;
            responseActive.current = true;
            setAssistantState('thinking');
            
            ws.current.send(
              JSON.stringify({
                type: 'audio',
                format: 'pcm_s16le',
                sample_rate: 16000,
                data: int16ToBase64(pcm16),
                vad_silence_ms: 650,
              })
            );
          } else {
            console.log('🔇 Slice too small / WS closed — re-arming listen');
            if (isMicEnabled.current && !isPlaying.current && !responseActive.current) {
              startListeningRef.current();
            }
          }
        },
        onVADMisfire: () => {
          console.log("❌ VAD misfire (ignored noise)");
          isSpeaking.current = false;
        }
      });
      myvad.current.start();

    } catch (err) {
      console.error('Mic access error:', err);
      isMicEnabled.current = false;
      setAssistantState('idle');
      useFridayStore.setState({ isMicActive: false });
    }
  }, [sendInterrupt, setAssistantState]);

  startListeningRef.current = startListening;

  const toggleMic = useCallback(async () => {
    if (audioContext.current?.state === 'suspended') {
      await audioContext.current.resume();
    }

    if (isMicEnabled.current) {
      console.log('🎤 Mic OFF');
      isMicEnabled.current = false;
      clearVad();
      clearBargeIn();
      isCapturing.current = false;
      stopTracks();
      useFridayStore.setState({ isMicActive: false });
      setAssistantState('idle');
    } else {
      console.log('🎤 Mic ON');
      responseActive.current = false;
      ignoreTts.current = false;
      isMicEnabled.current = true;
      await startListening();
    }
  }, [setAssistantState, startListening]);

  return { toggleMic };
}
