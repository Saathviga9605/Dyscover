export interface ReadingTask {
  task_id: string;
  expected_text: string;
  language: string;
  difficulty: number;
  content_type: 'word' | 'letter' | 'phrase' | 'sentence' | 'other';
  version: string;
}

export interface SpeechAnalysisResult {
  expected_text: string;
  heard_text: string;
  correct: boolean;
  confidence: number;
  duration_ms: number;
  mean_amplitude: number;
  peak_amplitude: number;
  transcript_similarity: number;
  provider: string;
  features: Record<string, number>;
}

export type SpeechProviderPhase = 'UNAVAILABLE' | 'NOT_CONFIGURED' | 'REQUESTED' | 'READY' | 'LISTENING' | 'PROCESSING' | 'ERROR';

export interface SpeechCapabilities {
  recognition: boolean;
  audio: boolean;
  secureContext: boolean;
}

export function probeSpeechCapabilities(): SpeechCapabilities {
  if (typeof window === 'undefined') return { recognition: false, audio: false, secureContext: false };
  const recognition =
    typeof window.SpeechRecognition !== 'undefined' || typeof (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition !== 'undefined';
  return {
    recognition,
    audio: typeof navigator !== 'undefined' && !!navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function',
    secureContext: window.isSecureContext,
  };
}

export function normalizeText(value: string, language = 'en'): string {
  const lower = value.toLowerCase().normalize(language === 'en' ? 'NFKD' : 'NFC');
  const stripped = language === 'en' ? lower.replace(/[\u0300-\u036f]/g, '') : lower;
  if (language === 'en') {
    return stripped
      .replace(/[^a-z0-9 ]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }
  // For non-English scripts (e.g. Tamil) keep Unicode letters, combining marks and numbers
  // so that transcripts are not reduced to empty text by an English-only filter.
  return stripped
    .replace(/[^\p{L}\p{M}\p{N} ]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function similarityRatio(a: string, b: string, language = 'en'): number {
  const left = normalizeText(a, language);
  const right = normalizeText(b, language);
  if (left === right) return 1;
  if (!left.length || !right.length) return 0;
  const distance = levenshtein(left, right);
  const longest = Math.max(left.length, right.length);
  return 1 - distance / longest;
}

export function decideCorrectness(similarity: number, difficulty: number): boolean {
  const threshold = difficulty >= 3 ? 0.66 : 0.6;
  return similarity >= threshold;
}

function levenshtein(a: string, b: string): number {
  const matrix: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 0; j <= b.length; j += 1) matrix[0][j] = j;
  for (let i = 1; i <= a.length; i += 1) {
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + cost);
    }
  }
  return matrix[a.length][b.length];
}