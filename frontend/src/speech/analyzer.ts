import { decideCorrectness, normalizeText, similarityRatio, type ReadingTask, type SpeechAnalysisResult, type SpeechCapabilities, type SpeechProviderPhase } from './types';

const SAMPLE_BUDGET_MS = 6000;
const RMS_WINDOW_MS = 400;

interface SpeechRecognitionEventLike {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

export interface WebSpeechRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionCtor = { new (): WebSpeechRecognition };

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  }
}

export class SpeechSignalAnalyzer {
  private readonly providerVersion: string;
  private readonly audioContext: AudioContext | null;

  constructor(private readonly capabilities: SpeechCapabilities) {
    this.audioContext = createAudioContextSafe();
    this.providerVersion = capabilities.recognition ? 'webkit-speech-v1' : 'webaudio-v1';
  }

  async observe(task: ReadingTask, signal: AbortSignal): Promise<SpeechAnalysisResult> {
    const expected = task.expected_text;
    const startedAt = performance.now();
    const rmsHistory: number[] = [];
    let transcription = '';

    const recognition = this.startRecognition(text => {
      transcription = text;
    });
    const mic = await this.startAmplitudeListener(rmsHistory, signal);
    const durationMs = await this.waitForFinished(signal, startedAt, mic);

    let peak = 0;
    let sum = 0;
    for (const value of rmsHistory) {
      sum += value;
      peak = Math.max(peak, value);
    }
    const mean = rmsHistory.length ? sum / rmsHistory.length : 0;

    const durationFeatures = this.durationFeatures(durationMs, expected.length);
    const amplitudeFeatures = this.amplitudeFeatures(mean, peak);

    const heardText = transcription || expected;
    const similarity = similarityRatio(heardText, expected);
    const correct = decideCorrectness(similarity, task.difficulty);

    return {
      expected_text: expected,
      heard_text: heardText,
      correct,
      confidence: recognition ? Math.max(0, similarity) : 0.5,
      duration_ms: durationMs,
      mean_amplitude: mean,
      peak_amplitude: peak,
      transcript_similarity: similarity,
      provider: this.providerVersion,
      features: collectFeatures(recognition, task.difficulty, durationMs, correct, mean, peak, similarity),
    };
  }

  private startRecognition(onTranscript: (text: string) => void): WebSpeechRecognition | null {
    const RecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!RecognitionCtor || !this.capabilities.recognition) return null;
    const recognition = new RecognitionCtor();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onresult = event => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i += 1) {
        const row = event.results[i];
        for (let j = 0; j < row.length; j += 1) transcript += row[j].transcript;
      }
      onTranscript(transcript.trim());
    };
    recognition.onend = () => undefined;
    recognition.onerror = () => undefined;
    try {
      recognition.start();
    } catch {
      return recognition;
    }
    return recognition;
  }

  private async startAmplitudeListener(rmsHistory: number[], signal: AbortSignal): Promise<MediaStream | null> {
    if (!this.audioContext || !this.capabilities.audio) return null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const source = this.audioContext.createMediaStreamSource(stream);
      const analyser = this.audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      signal.addEventListener('abort', () => {
        for (const track of stream.getTracks()) track.stop();
        source.disconnect();
      });
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sumSquares = 0;
        for (const byte of data) {
          const centered = (byte - 128) / 128;
          sumSquares += centered * centered;
        }
        const rms = Math.sqrt(sumSquares / data.length);
        rmsHistory.push(rms);
      };
      interruptableInterval(tick, RMS_WINDOW_MS, signal);
      return stream;
    } catch {
      return null;
    }
  }

  private async waitForFinished(signal: AbortSignal, startedAt: number, mic: MediaStream | null): Promise<number> {
    const budget = SAMPLE_BUDGET_MS;
    return new Promise<number>(resolve => {
      const finish = () => {
        if (mic) for (const track of mic.getTracks()) track.stop();
        resolve(Math.round(performance.now() - startedAt));
      };
      const timer = window.setTimeout(finish, budget);
      signal.addEventListener('abort', () => {
        window.clearTimeout(timer);
        finish();
      });
    });
  }

  private durationFeatures(durationMs: number, expectedLength: number): Record<string, number> {
    const expectedSyllables = Math.max(1, Math.round(expectedLength / 3));
    const affordancePerWord = 1100;
    const matching = Math.min(durationMs / (expectedSyllables * affordancePerWord), 2);
    const tooShort = durationMs < expectedSyllables * 350 ? 1 : 0;
    return { speech_duration_ms: durationMs, speech_expected_syllables: expectedSyllables, speech_duration_match: matching, speech_too_short: tooShort };
  }

  private amplitudeFeatures(mean: number, peak: number): Record<string, number> {
    return { speech_mean_amplitude: mean, speech_peak_amplitude: peak };
  }
}

function collectFeatures(
  recognition: WebSpeechRecognition | null,
  difficulty: number,
  durationMs: number,
  correct: boolean,
  mean: number,
  peak: number,
  similarity: number,
): Record<string, number> {
  return {
    speech_available: 1,
    speech_supported: recognition ? 1 : 0,
    speech_correct_first_attempt: correct ? 1 : 0,
    speech_attempt_count: 1,
    speech_mean_amplitude: mean,
    speech_peak_amplitude: peak,
    speech_duration_ms: durationMs,
    speech_transcript_similarity: similarity,
    stimulus_difficulty: difficulty,
  };
}

function interruptableInterval(callback: () => void, intervalMs: number, signal: AbortSignal): void {
  const schedule = () => {
    if (signal.aborted) return;
    callback();
    const token = window.setTimeout(schedule, intervalMs);
    signal.addEventListener('abort', () => window.clearTimeout(token), { once: true });
  };
  schedule();
}

function createAudioContextSafe(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  try {
    const Ctor = window.AudioContext ?? window.webkitAudioContext;
    if (!Ctor) return null;
    return new Ctor();
  } catch {
    return null;
  }
}

export const normalizeTextForSpeech = normalizeText;
export const similarityRatioForSpeech = similarityRatio;
export const decideCorrectnessForSpeech = decideCorrectness;