import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';

/** Tunable VAD / endpointing (energy VAD — not Silero). */
export const VAD_CONFIG = {
  /** Fallback if noise floor isn't ready yet. Speech-band energy, not all FFT bins. */
  SPEECH_THRESHOLD: 28,
  SILENCE_MS: 650,
  MAX_UTTERANCE_MS: 12000,
  VAD_POLL_MS: 50,
  NOISE_CALIBRATE_MS: 400,
  SPEECH_MARGIN: 16,
  SILENCE_MARGIN: 7,
} as const;

function speechBandEnergy(analyserNode: AnalyserNode, dataArray: Uint8Array): number {
  analyserNode.getByteFrequencyData(dataArray);
  const sampleRate = analyserNode.context.sampleRate || 48000;
  const binHz = sampleRate / analyserNode.fftSize;
  const lo = Math.max(1, Math.floor(300 / binHz));
  const hi = Math.min(dataArray.length - 1, Math.ceil(3400 / binHz));
  let sum = 0;
  let n = 0;
  for (let i = lo; i <= hi; i++) {
    sum += dataArray[i];
    n++;
  }
  return n ? sum / n : 0;
}

export const PCM_SAMPLE_RATE = 16000;

function floatToPcm16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function downsample(input: Float32Array, inRate: number, outRate: number): Float32Array {
  if (inRate === outRate) return input;
  const ratio = inRate / outRate;
  const outLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    out[i] = input[Math.min(input.length - 1, Math.floor(i * ratio))];
  }
  return out;
}

function concatInt16(chunks: Int16Array[]): Int16Array {
  let n = 0;
  for (const c of chunks) n += c.length;
  const out = new Int16Array(n);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
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

  const pcmChunks = useRef<Int16Array[]>([]);
  const pcmProcessor = useRef<ScriptProcessorNode | null>(null);
  const isCapturing = useRef(false);
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

      pcmChunks.current = [];
      const proc = audioContext.current.createScriptProcessor(4096, 1, 1);
      const mute = audioContext.current.createGain();
      mute.gain.value = 0;
      sourceNode.connect(proc);
      proc.connect(mute);
      mute.connect(audioContext.current.destination);
      pcmProcessor.current = proc;
      isCapturing.current = true;
      proc.onaudioprocess = (ev) => {
        if (!isCapturing.current) return;
        const input = ev.inputBuffer.getChannelData(0);
        const inRate = audioContext.current?.sampleRate || 48000;
        const ds = downsample(input, inRate, PCM_SAMPLE_RATE);
        pcmChunks.current.push(new Int16Array(floatToPcm16(ds)));
      };

      const SPEECH_THRESHOLD = VAD_CONFIG.SPEECH_THRESHOLD;
      const SILENCE_MS = VAD_CONFIG.SILENCE_MS;
      const MAX_UTTERANCE_MS = VAD_CONFIG.MAX_UTTERANCE_MS;
      const NOISE_CALIBRATE_MS = VAD_CONFIG.NOISE_CALIBRATE_MS;
      const SPEECH_MARGIN = VAD_CONFIG.SPEECH_MARGIN;
      const SILENCE_MARGIN = VAD_CONFIG.SILENCE_MARGIN;

      let speechStartedAt: number | null = null;
      let silenceStartedAt: number | null = null;
      let submitReason: 'silence' | 'max_utterance' | 'unknown' = 'unknown';
      let submitted = false;

      const stopCapture = () => {
        isCapturing.current = false;
        try {
          pcmProcessor.current?.disconnect();
        } catch {
          /* already disconnected */
        }
        pcmProcessor.current = null;
        stopTracks();
      };

      const submitUtterance = () => {
        if (submitted) return;
        submitted = true;
        clearVad();
        const stoppedAt = Date.now();
        const samples = concatInt16(pcmChunks.current);
        pcmChunks.current = [];
        stopCapture();

        if (!isMicEnabled.current) return;

        const speakMs = speechStartedAt ? stoppedAt - speechStartedAt : null;
        const bytes = samples.byteLength;
        console.log(
          `🎙️ PCM slice: ${bytes} bytes (${(bytes / (PCM_SAMPLE_RATE * 2)).toFixed(2)}s) | reason=${submitReason}` +
            (speakMs != null ? ` | since_speech_start=${speakMs}ms` : '')
        );

        if (bytes > 3200 && ws.current?.readyState === WebSocket.OPEN) {
          ignoreTts.current = false;
          responseActive.current = true;
          setAssistantState('thinking');
          const wsSendAt = Date.now();
          turnClock.current = {
            speechAt: speechStartedAt,
            silenceAt: silenceStartedAt,
            sendAt: wsSendAt,
            firstText: false,
            firstAudio: false,
            firstPlayback: false,
          };
          const speechToSend =
            speechStartedAt != null ? `${wsSendAt - speechStartedAt}ms` : '?';
          const silenceToSend =
            silenceStartedAt != null ? `${wsSendAt - silenceStartedAt}ms` : '?';
          console.log(
            `📤 Sending PCM to WebSocket @ ${new Date(wsSendAt).toISOString()}` +
              ` | from_speech=${speechToSend} | from_silence=${silenceToSend}` +
              ` | pcm=${bytes}B`
          );
          ws.current.send(
            JSON.stringify({
              type: 'audio',
              format: 'pcm_s16le',
              sample_rate: PCM_SAMPLE_RATE,
              data: int16ToBase64(samples),
              vad_silence_ms: SILENCE_MS,
              speech_ms: speakMs ?? undefined,
            })
          );
          console.log(
            `⏱️ [LATENCY] VAD silence gate=${SILENCE_MS}ms | speech≈${speakMs ?? '?'}ms | pcm→WS`
          );
        } else {
          console.log('🔇 Slice too small / WS closed — re-arming listen');
          if (isMicEnabled.current && !isPlaying.current && !responseActive.current) {
            startListeningRef.current();
          }
        }
      };

      isMicEnabled.current = true;
      isSpeaking.current = false;
      setAssistantState('listening');
      useFridayStore.setState({ isMicActive: true });
      console.log('🎧 Listening (PCM 16kHz)...');

      const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
      const startedAt = Date.now();
      let noiseFloor = 0;
      let noiseSamples = 0;
      let peakSpeech = 0;

      vadInterval.current = setInterval(() => {
        if (!isCapturing.current) {
          clearVad();
          return;
        }
        // Don't listen for end-of-utterance while we're still playing old TTS
        // (barge-in monitor handles that path)
        if (isPlaying.current) return;

        const utteredFor = speechStartedAt != null ? Date.now() - speechStartedAt : 0;
        if (isSpeaking.current && utteredFor > MAX_UTTERANCE_MS) {
          submitReason = 'max_utterance';
          console.log(
            `⏱️ Max utterance (${MAX_UTTERANCE_MS}ms) — submitting` +
              (speechStartedAt != null
                ? ` | spoke_for=${Date.now() - speechStartedAt}ms`
                : '')
          );
          clearVad();
          submitUtterance();
          return;
        }

        const avg = speechBandEnergy(analyserNode, dataArray);
        const elapsed = Date.now() - startedAt;
        if (!isSpeaking.current && elapsed < NOISE_CALIBRATE_MS) {
          noiseSamples += 1;
          noiseFloor += (avg - noiseFloor) / noiseSamples;
          return;
        }
        if (noiseFloor <= 0) noiseFloor = avg;

        const speechCut = Math.max(SPEECH_THRESHOLD, noiseFloor + SPEECH_MARGIN);
        const silenceCut = noiseFloor + SILENCE_MARGIN;

        if (avg > speechCut) {
          peakSpeech = Math.max(peakSpeech, avg);
          if (!isSpeaking.current) {
            speechStartedAt = Date.now();
            silenceStartedAt = null;
            console.log(
              `🗣️ Speech detected @ ${new Date(speechStartedAt).toISOString()}` +
                ` (avg=${avg.toFixed(1)} cut=${speechCut.toFixed(1)} noise=${noiseFloor.toFixed(1)})`
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
        } else if (
          isSpeaking.current &&
          !silenceTimer.current &&
          (avg < silenceCut || (peakSpeech > 0 && avg < peakSpeech * 0.45))
        ) {
          silenceStartedAt = Date.now();
          console.log(
            `🔇 User stopped speaking @ ${new Date(silenceStartedAt).toISOString()}` +
              (speechStartedAt != null
                ? ` | utterance=${silenceStartedAt - speechStartedAt}ms`
                : '') +
              ` | avg=${avg.toFixed(1)} silenceCut=${silenceCut.toFixed(1)} peak=${peakSpeech.toFixed(1)}` +
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
            submitUtterance();
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
      isCapturing.current = false;
      try {
        pcmProcessor.current?.disconnect();
      } catch {
        /* already disconnected */
      }
      pcmProcessor.current = null;
      stopTracks();
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
