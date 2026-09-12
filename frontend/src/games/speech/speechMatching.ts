import { normalizeText, similarityRatio } from '../../speech';
import type { SpeechPromptKind } from './speechGameContent';
import type { SpeechRecognitionResult } from './speechRecognition';

export const LETTER_NAME_ALIASES: Record<string, readonly string[]> = {
  a: ['a', 'ay'],
  b: ['b', 'bee'],
  c: ['c', 'see'],
  d: ['d', 'dee'],
  e: ['e', 'ee'],
  f: ['f', 'ef'],
  g: ['g', 'gee'],
  h: ['h', 'aitch'],
  i: ['i', 'eye'],
  j: ['j', 'jay'],
  k: ['k', 'kay'],
  l: ['l', 'el'],
  m: ['m', 'em'],
  n: ['n', 'en'],
  o: ['o', 'oh'],
  p: ['p', 'pee'],
  q: ['q', 'cue'],
  r: ['r', 'ar'],
  s: ['s', 'ess'],
  t: ['t', 'tee'],
  u: ['u', 'you'],
  v: ['v', 'vee'],
  w: ['w', 'double you'],
  x: ['x', 'ex'],
  y: ['y', 'why'],
  z: ['z', 'zee', 'zed'],
};

const CONFUSABLE_LETTER_PAIRS: Record<string, string> = { b: 'p', p: 'b', d: 't', t: 'd', m: 'n', n: 'm', u: 'v', v: 'u', q: 'k', k: 'q', s: 'z', z: 's' };

function phoneticKey(text: string): string {
  return normalizeText(text).replace(/[^a-z]/g, '');
}

export function phoneticSimilarity(a: string, b: string): number {
  const x = phoneticKey(a);
  const y = phoneticKey(b);
  if (!x.length || !y.length) return 0;
  if (x === y) return 1;
  let matches = 0;
  for (let i = 0; i < Math.min(x.length, y.length); i += 1) {
    if (x[i] === y[i] || CONFUSABLE_LETTER_PAIRS[x[i]] === y[i] || CONFUSABLE_LETTER_PAIRS[y[i]] === x[i]) matches += 1;
  }
  return matches / Math.max(x.length, y.length);
}

function aliasOptions(expected: string, kind: SpeechPromptKind): string[] {
  const options = new Set<string>();
  const key = normalizeText(expected);
  if (key && key.split(' ').length === 1) {
    const letter = normalizeText(expected).replace('.', '').trim();
    if (LETTER_NAME_ALIASES[letter]) for (const alias of LETTER_NAME_ALIASES[letter]) options.add(normalizeText(alias));
  }
  if (kind === 'letter') {
    const letter = normalizeText(expected).trim();
    if (LETTER_NAME_ALIASES[letter]) for (const alias of LETTER_NAME_ALIASES[letter]) options.add(normalizeText(alias));
  }
  options.add(key);
  return [...options].filter(Boolean);
}

function tokenize(text: string): string[] {
  const value = normalizeText(text);
  return value ? value.split(' ') : [];
}

function matchesOption(heard: string, option: string): boolean {
  if (!heard || !option) return false;
  if (heard === option || heard.includes(option) || option.includes(heard)) return true;
  return similarityRatio(heard, option) >= 0.72 || phoneticSimilarity(heard, option) >= 0.72;
}

export interface SpeechGrade {
  transcript: string;
  normalizedTranscript: string;
  expected: string;
  transcriptSimilarity: number;
  phoneticSimilarity: number;
  matchedVia: 'exact' | 'similar' | 'letter-name' | 'word-coverage' | 'none';
  correct: boolean;
}

const WORD_SIMILARITY_THRESHOLD = 0.66;
const SENTENCE_SIMILARITY_THRESHOLD = 0.55;
const RAN_SIMILARITY_THRESHOLD = 0.6;
const WORD_MATCH_THRESHOLD = 0.6;
const WORD_COVERAGE_THRESHOLD = 0.6;

export function gradeSpeechResponse(expectedText: string, kind: SpeechPromptKind, transcript: string): SpeechGrade {
  const heard = normalizeText(transcript);
  const expected = normalizeText(expectedText);
  const options = aliasOptions(expectedText, kind);

  const transcriptSimilarity = similarityRatio(heard, expected);
  let phonetic = phoneticSimilarity(heard, expected);
  for (const option of options) phonetic = Math.max(phonetic, phoneticSimilarity(heard, option));

  const optionsMatch = options.some(option => matchesOption(heard, option));
  const letterNameMatch = options.some(option => option && (heard === option || heard.includes(option)));
  const wholeSimilarity = Math.max(transcriptSimilarity, ...options.map(option => similarityRatio(heard, option)));
  const threshold = kind === 'word' ? WORD_SIMILARITY_THRESHOLD : kind === 'sentence' ? SENTENCE_SIMILARITY_THRESHOLD : RAN_SIMILARITY_THRESHOLD;

  if (kind === 'letter') {
    return {
      transcript,
      normalizedTranscript: heard,
      expected: expectedText,
      transcriptSimilarity,
      phoneticSimilarity: phonetic,
      matchedVia: letterNameMatch ? 'letter-name' : optionsMatch || wholeSimilarity >= threshold ? 'similar' : 'none',
      correct: letterNameMatch || optionsMatch || wholeSimilarity >= threshold,
    };
  }

  if (kind === 'letter-pair') {
    const targetLetters = tokenize(expected);
    const heardWords = tokenize(heard);
    const matchedLetters = targetLetters.filter(letter => {
      const aliases = aliasOptions(letter, 'letter');
      return heardWords.some(item => aliases.some(alias => matchesOption(item, alias)));
    }).length;
    const matched = matchedLetters >= targetLetters.length || optionsMatch;
    return {
      transcript,
      normalizedTranscript: heard,
      expected: expectedText,
      transcriptSimilarity,
      phoneticSimilarity: phonetic,
      matchedVia: matched ? 'letter-name' : 'none',
      correct: matched,
    };
  }

  if (kind === 'sentence' || kind === 'ran') {
    const expectedWords = kind === 'ran' ? tokenize(expected) : tokenize(expected);
    const heardWords = tokenize(heard);
    const covered = expectedWords.filter(word => heardWords.some(item => similarityRatio(item, word) >= WORD_MATCH_THRESHOLD || phoneticSimilarity(item, word) >= WORD_MATCH_THRESHOLD)).length;
    const coverage = expectedWords.length ? covered / expectedWords.length : 0;
    if (coverage >= WORD_COVERAGE_THRESHOLD) {
      return {
        transcript,
        normalizedTranscript: heard,
        expected: expectedText,
        transcriptSimilarity,
        phoneticSimilarity: phonetic,
        matchedVia: 'word-coverage',
        correct: true,
      };
    }
  }

  const correct = optionsMatch || wholeSimilarity >= threshold;
  const literalMatch = options.some(option => option && (heard === option || heard.includes(option)));
  return {
    transcript,
    normalizedTranscript: heard,
    expected: expectedText,
    transcriptSimilarity,
    phoneticSimilarity: phonetic,
    matchedVia: correct ? optionsMatch && literalMatch ? 'exact' : 'similar' : 'none',
    correct,
  };
}

export function singleLetterName(promptText: string): string | null {
  const key = normalizeText(promptText);
  if (key.length !== 1) return null;
  return LETTER_NAME_ALIASES[key]?.[1] ?? key;
}

export function speechGradeError(errorType?: string): string | null {
  if (!errorType) return null;
  if (errorType === 'no-speech') return 'no speech heard';
  if (errorType === 'not-allowed' || errorType === 'service-not-allowed') return 'microphone not allowed';
  if (errorType === 'audio-capture') return 'microphone unavailable';
  if (errorType === 'aborted') return 'stopped';
  return errorType;
}

export function gradeFromRecognition(expectedText: string, kind: SpeechPromptKind, result: SpeechRecognitionResult): SpeechGrade & { errorType?: string } {
  if (result.errorType) {
    return {
      transcript: '',
      normalizedTranscript: '',
      expected: expectedText,
      transcriptSimilarity: 0,
      phoneticSimilarity: 0,
      matchedVia: 'none',
      correct: false,
      errorType: result.errorType,
    };
  }
  return gradeSpeechResponse(expectedText, kind, result.transcript);
}