import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';

/** Tunable VAD / endpointing (energy VAD — not Silero). */
export const VAD_CONFIG = {
  SPEECH_THRESHOLD: 22,
  SILENCE_MS: 800, // was 1500 — still safe against premature cutoffs
  MAX_UTTERANCE_MS: 12000,
  VAD_POLL_MS: 50,
} as const;

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

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const isMicEnabled = useRef(false);
  const mediaStream = useRef<MediaStream | null>(null);

  const analyser = useRef<AnalyserNode | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const vadInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const bargeInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const bargeGraceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakingStartedAt = useRef(0);
  const isSpeaking = useRef(false);
  const startListeningRef = useRef<() => Promise<void>>(async () => {});
  const interruptRef = useRef<() => void>(() => {});

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

    if (!isPlaying.current) {
      speakingStartedAt.current = Date.now();
    }
    isPlaying.current = true;
    setAssistantState('speaking');

    if (audioContext.current?.state === 'suspended') {
      await audioContext.current.resume();
    }

    const buffer = audioQueue.current.shift()!;
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
    const BARGE_THRESHOLD = 30;
    const REQUIRED_HITS = 30; // ~1.5s sustained user speech before stop (50ms ticks)

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
          case 'transcription':
            console.log('📝 Transcription:', payload);
            ignoreTts.current = false;
            responseActive.current = true;
            setAssistantState('thinking');
            break;

          case 'interrupted':
            console.log('⛔ Backend interrupted:', payload);
            ignoreTts.current = true;
            responseActive.current = false;
            stopPlayback();
            break;

          case 'ai_audio_chunk':
            if (ignoreTts.current) {
              console.log('⏭️ Dropping TTS chunk (interrupted)');
              break;
            }
            responseActive.current = true;
            try {
              const binaryString = window.atob(payload);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              const audioBuf = await audioContext.current!.decodeAudioData(bytes.buffer);
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

          case 'ai_text_complete':
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
      if (mediaRecorder.current && mediaRecorder.current.state === 'recording') return;
      // Between TTS chunks only — never block an explicit mic-on (responseActive cleared in toggleMic)
      if (responseActive.current && !isPlaying.current && audioQueue.current.length === 0) {
        // Stale flag after TTS: clear and continue
        responseActive.current = false;
      }

      // If FRIDAY is talking, cut her off first
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

      const SPEECH_THRESHOLD = VAD_CONFIG.SPEECH_THRESHOLD;
      const SILENCE_MS = VAD_CONFIG.SILENCE_MS;
      const MAX_UTTERANCE_MS = VAD_CONFIG.MAX_UTTERANCE_MS;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };

      // Timing for this listen slice (speech → silence → WS send)
      let speechStartedAt: number | null = null;
      let silenceStartedAt: number | null = null;
      let submitReason: 'silence' | 'max_utterance' | 'unknown' = 'unknown';

      recorder.onstop = async () => {
        clearVad();
        const stoppedAt = Date.now();
        const audioBlob = new Blob(audioChunks.current, { type: mime });
        audioChunks.current = [];
        stopTracks();
        mediaRecorder.current = null;

        if (!isMicEnabled.current) return;

        const speakMs = speechStartedAt ? stoppedAt - speechStartedAt : null;
        const silenceWaitMs =
          silenceStartedAt && speechStartedAt ? stoppedAt - silenceStartedAt : null;

        console.log(
          `🎙️ Slice size: ${audioBlob.size} bytes | reason=${submitReason}` +
            (speakMs != null ? ` | since_speech_start=${speakMs}ms` : '') +
            (silenceWaitMs != null ? ` | since_silence_start=${silenceWaitMs}ms` : '')
        );

        if (audioBlob.size > 1500 && ws.current?.readyState === WebSocket.OPEN) {
          const buffer = await audioBlob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = '';
          for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
          const base64 = window.btoa(binary);

          ignoreTts.current = false;
          responseActive.current = true;
          setAssistantState('thinking');
          const wsSendAt = Date.now();
          console.log(
            `📤 Sending audio to WebSocket @ ${new Date(wsSendAt).toISOString()}` +
              (speechStartedAt != null
                ? ` | total_from_speech_detect=${wsSendAt - speechStartedAt}ms`
                : '') +
              (silenceStartedAt != null
                ? ` | from_user_stop=${wsSendAt - silenceStartedAt}ms (includes ${SILENCE_MS}ms silence gate)`
                : '')
          );
          ws.current.send(
            JSON.stringify({
              type: 'audio',
              data: base64,
              vad_silence_ms: SILENCE_MS,
              speech_ms: speakMs ?? undefined,
            })
          );
          console.log(
            `⏱️ [LATENCY] VAD silence gate=${SILENCE_MS}ms | speech≈${speakMs ?? '?'}ms | blob→WS`
          );
        } else {
          console.log('🔇 Slice too small / WS closed — re-arming listen');
          if (isMicEnabled.current && !isPlaying.current && !responseActive.current) {
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
      const startedAt = Date.now();

      vadInterval.current = setInterval(() => {
        if (!mediaRecorder.current || mediaRecorder.current.state !== 'recording') {
          clearVad();
          return;
        }
        // Don't listen for end-of-utterance while we're still playing old TTS
        // (barge-in monitor handles that path)
        if (isPlaying.current) return;

        if (Date.now() - startedAt > MAX_UTTERANCE_MS && isSpeaking.current) {
          submitReason = 'max_utterance';
          console.log(
            `⏱️ Max utterance (${MAX_UTTERANCE_MS}ms) — submitting` +
              (speechStartedAt != null
                ? ` | spoke_for=${Date.now() - speechStartedAt}ms`
                : '')
          );
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
            speechStartedAt = Date.now();
            silenceStartedAt = null;
            console.log(
              `🗣️ Speech detected @ ${new Date(speechStartedAt).toISOString()} (avg=${avg.toFixed(1)})`
            );
            isSpeaking.current = true;
          }
          // User started talking again before silence timer fired
          if (silenceTimer.current) {
            clearTimeout(silenceTimer.current);
            silenceTimer.current = null;
            if (silenceStartedAt != null) {
              console.log(
                `🗣️ Speech resumed — cancelled silence timer after ${Date.now() - silenceStartedAt}ms`
              );
              silenceStartedAt = null;
            }
          }
        } else if (isSpeaking.current && !silenceTimer.current) {
          silenceStartedAt = Date.now();
          console.log(
            `🔇 User stopped speaking @ ${new Date(silenceStartedAt).toISOString()}` +
              (speechStartedAt != null
                ? ` | utterance=${silenceStartedAt - speechStartedAt}ms`
                : '') +
              ` | starting ${SILENCE_MS}ms silence timer…`
          );
          silenceTimer.current = setTimeout(() => {
            const firedAt = Date.now();
            submitReason = 'silence';
            console.log(
              `✅ Silence timer fired @ ${new Date(firedAt).toISOString()}` +
                ` | waited=${firedAt - (silenceStartedAt ?? firedAt)}ms → stop recorder → WS next`
            );
            silenceTimer.current = null;
            isSpeaking.current = false;
            clearVad();
            if (mediaRecorder.current?.state === 'recording') {
              mediaRecorder.current.stop();
            }
          }, SILENCE_MS);
        }
      }, VAD_CONFIG.VAD_POLL_MS);
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
      if (mediaRecorder.current?.state === 'recording') {
        mediaRecorder.current.stop();
      } else {
        stopTracks();
      }
      useFridayStore.setState({ isMicActive: false });
      setAssistantState('idle');
    } else {
      console.log('🎤 Mic ON');
      // Explicit user mic-on must not be blocked by sticky responseActive from prior TTS
      responseActive.current = false;
      ignoreTts.current = false;
      isMicEnabled.current = true;
      await startListening();
    }
  }, [setAssistantState, startListening]);

  return { toggleMic };
}
