/** Coordinates VAD events with assistant playback without browser audio APIs. */
export type VoiceTurnCallbacks = {
  onBargeIn: () => void;
  onUtterance: (audio: Float32Array) => void;
};

export class VoiceTurnController {
  private micEnabled = false;
  private assistantActive = false;
  private speechActive = false;
  private bargeInSent = false;
  private readonly callbacks: VoiceTurnCallbacks;

  constructor(callbacks: VoiceTurnCallbacks) {
    this.callbacks = callbacks;
  }

  setMicEnabled(enabled: boolean): void {
    this.micEnabled = enabled;
    if (!enabled) {
      this.speechActive = false;
      this.bargeInSent = false;
    }
  }

  setAssistantActive(active: boolean): void {
    this.assistantActive = active;
  }

  onSpeechStart(): void {
    if (!this.micEnabled) return;
    this.speechActive = true;
  }

  /** Call only after Silero confirms a real utterance, not on a VAD candidate. */
  onSpeechRealStart(): void {
    if (!this.micEnabled || !this.speechActive || !this.assistantActive || this.bargeInSent) return;
    this.bargeInSent = true;
    this.assistantActive = false;
    this.callbacks.onBargeIn();
  }

  onSpeechEnd(audio: Float32Array): void {
    if (!this.micEnabled || !this.speechActive) return;
    this.speechActive = false;
    this.bargeInSent = false;
    if (audio.length > 1600) this.callbacks.onUtterance(audio);
  }

  onMisfire(): void {
    this.speechActive = false;
    this.bargeInSent = false;
  }
}
