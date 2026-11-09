import { useEffect, useRef, useCallback } from 'react';
import { useFridayStore } from '../store/useFridayStore';
import { MicVAD } from "@ricky0123/vad-web";
import { VoiceTurnController } from './voiceTurnController';

export const PCM_SAMPLE_RATE = 16000;

type VadProbabilityWindow = {
  startedAt: number;
  frames: number;
  probabilitySum: number;
  probabilityPeak: number;
  aboveThreshold: number;
  rmsSum: number;
};

function newVadProbabilityWindow(): VadProbabilityWindow {
  return { startedAt: Date.now(), frames: 0, probabilitySum: 0, probabilityPeak: 0, aboveThreshold: 0, rmsSum: 0 };
}

function audioSignalStats(samples: Float32Array) {
  let sumSquares = 0;
  let peak = 0;
  let clippedSamples = 0;
  for (const sample of samples) {
    const magnitude = Math.abs(sample);
    sumSquares += sample * sample;
    peak = Math.max(peak, magnitude);
    if (magnitude >= 0.999) clippedSamples++;
  }
  const rms = samples.length ? Math.sqrt(sumSquares / samples.length) : 0;
  return { rms: Number(rms.toFixed(4)), peak: Number(peak.toFixed(4)), clippedSamples };
}

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
  const micGeneration = useRef(0);
  const mediaStream = useRef<MediaStream | null>(null);
  const myvad = useRef<any>(null);

  const startListeningRef = useRef<() => Promise<void>>(async () => {});
  const voiceTurn = useRef<VoiceTurnController | null>(null);
  const vadProbabilityWindow = useRef(newVadProbabilityWindow());
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

  const stopPlayback = useCallback(() => {
    try {
      currentSource.current?.stop();
    } catch {
      /* already stopped */
    }
    currentSource.current = null;
    audioQueue.current = [];
    isPlaying.current = false;
    voiceTurn.current?.setAssistantActive(false);
  }, []);

  const sendInterrupt = useCallback((source: string = 'unspecified') => {
    console.info('[VOICE INTERRUPT] requested', {
      source,
      at: new Date().toISOString(),
      isPlaying: isPlaying.current,
      queuedAudioChunks: audioQueue.current.length,
      responseActive: responseActive.current,
      micEnabled: isMicEnabled.current,
    });
    ignoreTts.current = true;
    responseActive.current = false;
    stopPlayback();
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'interrupt' }));
      console.log('⛔ Sent interrupt to FRIDAY');
    }
    setAssistantState(isMicEnabled.current ? 'listening' : 'idle');
  }, [setAssistantState, stopPlayback]);

  if (!voiceTurn.current) {
    voiceTurn.current = new VoiceTurnController({
      onBargeIn: () => sendInterrupt('silero_real_speech'),
      onUtterance: (audio) => {
        const pcm16 = floatToPcm16(audio);
        if (pcm16.byteLength <= 3200 || ws.current?.readyState !== WebSocket.OPEN) {
          console.warn('[VAD AUDIO] dropped segment', {
            bytes: pcm16.byteLength,
            websocketState: ws.current?.readyState,
            reason: pcm16.byteLength <= 3200 ? 'below_minimum_size' : 'websocket_not_open',
          });
          return;
        }
        ignoreTts.current = false;
        responseActive.current = true;
        setAssistantState('thinking');
        console.info('[VAD AUDIO] submitting segment', {
          durationMs: Math.round(audio.length / PCM_SAMPLE_RATE * 1000),
          pcmBytes: pcm16.byteLength,
          ...audioSignalStats(audio),
          assistantPlaying: isPlaying.current,
          queuedAudioChunks: audioQueue.current.length,
          at: new Date().toISOString(),
        });
        ws.current.send(JSON.stringify({
          type: 'audio',
          format: 'pcm_s16le',
          sample_rate: PCM_SAMPLE_RATE,
          data: int16ToBase64(pcm16),
          vad_silence_ms: 650,
          speech_ms: Math.round(audio.length / PCM_SAMPLE_RATE * 1000),
        }));
      },
    });
  }

  const playNextInQueue = useCallback(async () => {
    if (ignoreTts.current) {
      audioQueue.current = [];
      isPlaying.current = false;
      return;
    }

    if (audioQueue.current.length === 0) {
      isPlaying.current = false;
      voiceTurn.current?.setAssistantActive(responseActive.current);
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
    isPlaying.current = true;
    voiceTurn.current?.setAssistantActive(true);
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
            voiceTurn.current?.setAssistantActive(true);
            setAssistantState('thinking');
            break;
          }

          case 'interrupted':
            // A cancellation from the previous turn can arrive after the next
            // utterance has already been submitted. Do not drop that turn's audio.
            if (responseActive.current) {
              console.log('⏭️ Ignoring stale interruption after next turn began');
              break;
            }
            console.log('⛔ Backend interrupted:', payload);
            ignoreTts.current = true;
            responseActive.current = false;
            stopPlayback();
            voiceTurn.current?.setAssistantActive(false);
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
              if (!isPlaying.current) playNextInQueue();
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
            voiceTurn.current?.setAssistantActive(
              isPlaying.current || audioQueue.current.length > 0,
            );
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
            voiceTurn.current?.setAssistantActive(false);
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
      micGeneration.current += 1;
      clearTimeout(reconnectTimeout!);
      const vad = myvad.current;
      myvad.current = null;
      if (vad) void vad.destroy();
      voiceTurn.current?.setMicEnabled(false);
      const stream = mediaStream.current;
      mediaStream.current = null;
      stream?.getTracks().forEach((track) => track.stop());
      stopPlayback();
      if (ws.current) ws.current.close();
      if (audioContext.current) audioContext.current.close();
    };
  }, [playNextInQueue, setAssistantState, stopPlayback]);

  const startListening = useCallback(async () => {
    if (isCapturing.current) return;
    const generation = ++micGeneration.current;
    isCapturing.current = true;
    let stream: MediaStream | null = null;
    let vad: any = null;

    try {
      if (responseActive.current && !isPlaying.current && audioQueue.current.length === 0) {
        responseActive.current = false;
      }

      if (isPlaying.current || audioQueue.current.length > 0) {
        sendInterrupt('listen_restart');
      }

      if (audioContext.current?.state === 'suspended') {
        await audioContext.current.resume();
      }
      if (!audioContext.current) {
        audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (generation !== micGeneration.current || !isMicEnabled.current) {
        stream.getTracks().forEach((track) => track.stop());
        if (generation === micGeneration.current) isCapturing.current = false;
        return;
      }
      mediaStream.current = stream;
      const activeStream = stream;

      isMicEnabled.current = true;
      voiceTurn.current?.setMicEnabled(true);
      setAssistantState('listening');
      useFridayStore.setState({ isMicActive: true });
      console.log('🎧 Listening (Silero AI VAD)...');

      vad = await MicVAD.new({
        getStream: async () => activeStream,
        positiveSpeechThreshold: 0.5,
        redemptionMs: 650,
        baseAssetPath: "/",
        onnxWASMBasePath: "/",
        model: "legacy",
        onSpeechStart: () => {
          console.info('[VAD] speech_candidate_start', {
            at: new Date().toISOString(),
            assistantPlaying: isPlaying.current,
            responseActive: responseActive.current,
            queuedAudioChunks: audioQueue.current.length,
            probabilityWindow: { ...vadProbabilityWindow.current },
          });
          voiceTurn.current?.onSpeechStart();
        },
        onSpeechRealStart: () => {
          console.info('[VAD] speech_confirmed', {
            at: new Date().toISOString(),
            assistantPlaying: isPlaying.current,
            responseActive: responseActive.current,
            queuedAudioChunks: audioQueue.current.length,
            probabilityWindow: { ...vadProbabilityWindow.current },
          });
          voiceTurn.current?.onSpeechRealStart();
        },
        onSpeechEnd: (audio) => {
          console.info('[VAD] speech_end', {
            at: new Date().toISOString(),
            durationMs: Math.round(audio.length / PCM_SAMPLE_RATE * 1000),
            sampleCount: audio.length,
            ...audioSignalStats(audio),
            assistantPlaying: isPlaying.current,
            responseActive: responseActive.current,
            queuedAudioChunks: audioQueue.current.length,
          });
          voiceTurn.current?.onSpeechEnd(audio);
        },
        onVADMisfire: () => {
          console.info('[VAD] misfire', {
            at: new Date().toISOString(),
            assistantPlaying: isPlaying.current,
            responseActive: responseActive.current,
            probabilityWindow: { ...vadProbabilityWindow.current },
          });
          voiceTurn.current?.onMisfire();
        },
        onFrameProcessed: ({ isSpeech }, frame) => {
          const window = vadProbabilityWindow.current;
          let sumSquares = 0;
          for (const sample of frame) sumSquares += sample * sample;
          window.frames++;
          window.probabilitySum += isSpeech;
          window.probabilityPeak = Math.max(window.probabilityPeak, isSpeech);
          if (isSpeech >= 0.5) window.aboveThreshold++;
          window.rmsSum += frame.length ? Math.sqrt(sumSquares / frame.length) : 0;

          const elapsedMs = Date.now() - window.startedAt;
          if (elapsedMs >= 5000) {
            console.info('[VAD] probability_window', {
              durationMs: elapsedMs,
              frames: window.frames,
              meanSpeechProbability: window.frames
                ? Number((window.probabilitySum / window.frames).toFixed(3))
                : 0,
              peakSpeechProbability: Number(window.probabilityPeak.toFixed(3)),
              framesAtOrAboveThreshold: window.aboveThreshold,
              meanFrameRms: window.frames ? Number((window.rmsSum / window.frames).toFixed(4)) : 0,
              assistantPlaying: isPlaying.current,
              responseActive: responseActive.current,
            });
            vadProbabilityWindow.current = newVadProbabilityWindow();
          }
        }
      });
      const trackSettings = activeStream.getAudioTracks()[0]?.getSettings();
      console.info('[VAD] microphone_ready', {
        at: new Date().toISOString(),
        sampleRate: trackSettings?.sampleRate,
        channelCount: trackSettings?.channelCount,
        echoCancellation: trackSettings?.echoCancellation,
        noiseSuppression: trackSettings?.noiseSuppression,
        autoGainControl: trackSettings?.autoGainControl,
        model: 'legacy',
        positiveSpeechThreshold: 0.5,
        redemptionMs: 650,
      });
      if (generation !== micGeneration.current || !isMicEnabled.current) {
        await vad.destroy();
        stream.getTracks().forEach((track) => track.stop());
        if (mediaStream.current === stream) mediaStream.current = null;
        return;
      }
      myvad.current = vad;
      await vad.start();
      if (generation !== micGeneration.current || !isMicEnabled.current) {
        if (myvad.current === vad) {
          myvad.current = null;
          await vad.destroy();
        }
        activeStream.getTracks().forEach((track) => track.stop());
        if (mediaStream.current === activeStream) mediaStream.current = null;
      }

    } catch (err) {
      console.error('Mic access error:', err);
      if (generation !== micGeneration.current) return;
      if (myvad.current === vad) myvad.current = null;
      if (vad) await vad.destroy().catch(() => undefined);
      stream?.getTracks().forEach((track) => track.stop());
      if (mediaStream.current === stream) mediaStream.current = null;
      if (generation !== micGeneration.current) return;
      voiceTurn.current?.setMicEnabled(false);
      isCapturing.current = false;
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
      micGeneration.current += 1;
      isMicEnabled.current = false;
      voiceTurn.current?.setMicEnabled(false);
      isCapturing.current = false;
      const vad = myvad.current;
      myvad.current = null;
      const stream = mediaStream.current;
      mediaStream.current = null;
      if (vad) await vad.destroy();
      stream?.getTracks().forEach((track) => track.stop());
      useFridayStore.setState({ isMicActive: false });
      setAssistantState('idle');
    } else {
      console.log('🎤 Mic ON');
      responseActive.current = false;
      ignoreTts.current = false;
      isMicEnabled.current = true;
      voiceTurn.current?.setMicEnabled(true);
      await startListening();
    }
  }, [setAssistantState, startListening]);

  return { toggleMic };
}
