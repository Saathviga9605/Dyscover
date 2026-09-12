export type SpeechRecognitionErrorType = 'no-speech' | 'not-allowed' | 'service-not-allowed' | 'audio-capture' | 'network' | 'aborted' | 'unknown';

export interface SpeechRecognitionResult {
  transcript: string;
  confidence: number;
  latencyMs: number;
  durationMs: number;
  speechDetected: boolean;
  provider: string;
  errorType?: SpeechRecognitionErrorType;
  retriedNoSpeech: number;
}

export interface SpeechRecognitionControllerOptions {
  lang?: string;
  maxAlternatives?: number;
  budgetMs?: number;
  maxNoSpeechRetries?: number;
  onInterim?: (transcript: string) => void;
  onSpeechStart?: () => void;
}

interface SpeechRecognizedPhrase {
  transcript: string;
  confidence?: number;
}

interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognizedPhrase[] & { isFinal?: boolean }>;
}

interface WebSpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onspeechstart: (() => void) | null;
  onaudiostart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionCtor = { new (): WebSpeechRecognitionLike };

export function createRecognitionInstance(): WebSpeechRecognitionLike | null {
  if (typeof window === 'undefined') return null;
  const Ctor = (window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }).SpeechRecognition
    ?? (window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition;
  if (!Ctor) return null;
  try {
    return new Ctor();
  } catch {
    return null;
  }
}

export const SPEECH_PROVIDER_NAME = 'webkit-speech-v1';
const DEFAULT_BUDGET_MS = 12000;

export function speechSupported(): boolean {
  return typeof window !== 'undefined'
    && Boolean((window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }).SpeechRecognition
      ?? (window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }).webkitSpeechRecognition);
}

interface Deferred {
  promise: Promise<SpeechRecognitionResult>;
  resolve: (value: SpeechRecognitionResult) => void;
}

function deferred(): Deferred {
  let resolve!: (value: SpeechRecognitionResult) => void;
  const promise = new Promise<SpeechRecognitionResult>(res => {
    resolve = res;
  });
  return { promise, resolve };
}

export class SpeechRecognitionController {
  private readonly lang: string;
  private readonly maxAlternatives: number;
  private readonly budgetMs: number;
  private readonly maxNoSpeechRetries: number;
  private readonly onInterim?: (transcript: string) => void;
  private readonly onSpeechStart?: () => void;
  private recognition: WebSpeechRecognitionLike | null = null;
  private timer: number | undefined = undefined;
  private startedAt = 0;
  private speechStartedAt = 0;
  private noSpeechRetries = 0;
  private active = false;
  private pending: Deferred | null = null;

  constructor(options: SpeechRecognitionControllerOptions = {}) {
    this.lang = options.lang ?? 'en-US';
    this.maxAlternatives = options.maxAlternatives ?? 3;
    this.budgetMs = options.budgetMs ?? DEFAULT_BUDGET_MS;
    this.maxNoSpeechRetries = options.maxNoSpeechRetries ?? 2;
    this.onInterim = options.onInterim;
    this.onSpeechStart = options.onSpeechStart;
  }

  async start(): Promise<SpeechRecognitionResult> {
    if (this.active || this.pending) throw new Error('Recognition is already running.');
    this.active = true;
    this.startedAt = performance.now();
    this.speechStartedAt = 0;
    this.noSpeechRetries = 0;
    this.pending = deferred();

    const recognition = createRecognitionInstance();
    this.recognition = recognition;
    if (!recognition) {
      const promise = this.pending.promise;
      this.settle(this.errorResult('unknown'));
      return promise;
    }

    recognition.lang = this.lang;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = this.maxAlternatives;

    recognition.onaudiostart = () => undefined;
    recognition.onspeechstart = () => {
      if (!this.speechStartedAt) this.speechStartedAt = performance.now();
      this.onSpeechStart?.();
    };
    recognition.onresult = (event) => {
      let final = '';
      let confidence = 0;
      for (let i = 0; i < event.results.length; i += 1) {
        const row = event.results[i];
        const first = row[0];
        const isFinal = Boolean(row.isFinal);
        if (first && typeof first.transcript === 'string') {
          if (isFinal) {
            final += first.transcript;
            confidence = Math.max(confidence, first.confidence ?? 0);
          } else {
            this.onInterim?.(first.transcript.trim());
          }
        }
      }
      if (final.trim()) {
        this.settle({
          transcript: final.trim(),
          confidence,
          latencyMs: this.speechStartedAt ? Math.round(this.speechStartedAt - this.startedAt) : 0,
          durationMs: Math.round(performance.now() - this.startedAt),
          speechDetected: true,
          provider: SPEECH_PROVIDER_NAME,
          retriedNoSpeech: 0,
        });
      }
    };
    recognition.onerror = (event) => {
      const code = (event.error as string) ?? 'unknown';
      if (code === 'no-speech' && this.noSpeechRetries < this.maxNoSpeechRetries) {
        this.noSpeechRetries += 1;
        window.setTimeout(() => {
          if (!this.called() && this.recognition) {
            try {
              this.recognition.start();
            } catch {
              this.settle(this.errorResult('audio-capture'));
            }
          }
        }, 500);
        return;
      }
      if (code === 'no-speech') {
        this.settle(this.errorResult('no-speech'));
        return;
      }
      const type = (['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'aborted'] as const).includes(code as never)
        ? (code as SpeechRecognitionErrorType)
        : 'unknown';
      this.settle(this.errorResult(type));
    };
    recognition.onend = () => undefined;

    this.timer = window.setTimeout(() => {
      if (!this.called()) this.settle(this.errorResult(this.speechStartedAt ? 'unknown' : 'no-speech'));
    }, this.budgetMs);

    try {
      recognition.start();
    } catch {
      this.settle(this.errorResult('audio-capture'));
    }
    return this.pending.promise;
  }

  abort(): void {
    if (!this.active) return;
    this.settle(this.errorResult('aborted'));
  }

  private called(): boolean {
    return this.pending === null;
  }

  private settle(result: SpeechRecognitionResult): void {
    const pending = this.pending;
    this.cleanup();
    result.retriedNoSpeech = result.retriedNoSpeech ?? this.noSpeechRetries;
    pending?.resolve(result);
  }

  private cleanup(): void {
    if (this.recognition) {
      const instance = this.recognition;
      this.recognition = null;
      instance.onresult = null;
      instance.onend = null;
      instance.onerror = null;
      instance.onspeechstart = null;
      instance.onaudiostart = null;
      try {
        instance.abort();
      } catch {
        // Already stopped.
      }
    }
    window.clearTimeout(this.timer);
    this.pending = null;
    this.active = false;
  }

  private errorResult(errorType: SpeechRecognitionErrorType, durationMs?: number): SpeechRecognitionResult {
    return {
      transcript: '',
      confidence: 0,
      latencyMs: 0,
      durationMs: durationMs ?? Math.round(performance.now() - this.startedAt),
      speechDetected: Boolean(this.speechStartedAt),
      provider: SPEECH_PROVIDER_NAME,
      errorType,
      retriedNoSpeech: this.noSpeechRetries,
    };
  }
}