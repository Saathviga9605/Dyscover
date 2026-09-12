import { normalizeText } from '../../speech';
import type { SpeechGrade } from './speechMatching';
import type { SpeechRecognitionResult } from './speechRecognition';
import type { SpeechPromptKind } from './speechGameContent';

export const resultProvider = 'webkit-speech-v1';

export interface SpeechTrialEvidence {
  taskId: string;
  expectedText: string;
  kind: SpeechPromptKind;
  level: number;
  transcript: string;
  normalizedTranscript: string;
  transcriptSimilarity: number;
  phoneticSimilarity: number;
  confidence: number;
  latencyMs: number;
  durationMs: number;
  speechDetected: boolean;
  matchedVia: string;
  correct: boolean;
  errorType?: string;
  retriedNoSpeech: number;
}

export function buildSpeechEvidence(task: {
  taskId: string;
  expectedText: string;
  kind: SpeechPromptKind;
  level: number;
}, result: SpeechRecognitionResult, grade: SpeechGrade): SpeechTrialEvidence {
  const tokenizedExpected = normalizeText(task.expectedText).split(' ').filter(Boolean);
  return {
    taskId: task.taskId,
    expectedText: task.expectedText,
    kind: task.kind,
    level: task.level,
    transcript: result.transcript,
    normalizedTranscript: grade.normalizedTranscript,
    transcriptSimilarity: grade.transcriptSimilarity,
    phoneticSimilarity: grade.phoneticSimilarity,
    confidence: result.confidence,
    latencyMs: result.latencyMs,
    durationMs: result.durationMs,
    speechDetected: result.speechDetected,
    matchedVia: grade.matchedVia,
    correct: grade.correct,
    errorType: result.errorType,
    retriedNoSpeech: result.retriedNoSpeech,
  };
}

export function numericFeatures(evidence: SpeechTrialEvidence): Record<string, number> {
  const expectedTokens = normalizeText(evidence.expectedText).split(' ').filter(Boolean);
  const transcriptTokens = normalizeText(evidence.normalizedTranscript).split(' ').filter(Boolean);
  const uniqueExpected = new Set(expectedTokens);
  const covered = expectedTokens.filter(word => transcriptTokens.includes(word)).length;
  const coverage = expectedTokens.length ? covered / expectedTokens.length : 0;
  const uniqueTranscript = new Set(transcriptTokens);
  return {
    speech_available: 1,
    speech_supported: 1,
    speech_correct_first_attempt: evidence.correct ? 1 : 0,
    speech_attempt_count: 1,
    speech_speech_detected: evidence.speechDetected ? 1 : 0,
    speech_no_speech_retries: evidence.retriedNoSpeech,
    speech_transcript_similarity: evidence.transcriptSimilarity,
    speech_phonetic_similarity: evidence.phoneticSimilarity,
    speech_latency_ms: evidence.latencyMs,
    speech_reading_duration_ms: evidence.durationMs,
    speech_response_timing_available: 1,
    speech_expected_token_count: expectedTokens.length,
    speech_transcript_token_count: transcriptTokens.length,
    speech_word_coverage: coverage,
    text_token_count: expectedTokens.length,
    text_unique_token_count: uniqueExpected.size,
    text_type_token_ratio: expectedTokens.length ? uniqueExpected.size / expectedTokens.length : 0,
    speech_transcript_token_ratio: transcriptTokens.length ? uniqueTranscript.size / transcriptTokens.length : 0,
    stimulus_difficulty: evidence.level,
    speech_task_kind: kindCode(evidence.kind),
  };
}

function kindCode(kind: SpeechPromptKind): number {
  switch (kind) {
    case 'letter':
      return 1;
    case 'letter-pair':
      return 2;
    case 'word':
      return 3;
    case 'ran':
      return 4;
    case 'sentence':
      return 5;
    default:
      return 0;
  }
}

export function featureRecords(features: Record<string, number>): Record<string, { value: number; available: boolean }> {
  const records: Record<string, { value: number; available: boolean }> = {};
  for (const [name, value] of Object.entries(features)) {
    if (!Number.isFinite(value)) continue;
    records[name] = { value, available: true };
  }
  return records;
}

export function responseSubmittedPayload(evidence: SpeechTrialEvidence): Record<string, unknown> {
  return {
    modality: 'speech',
    task_id: evidence.taskId,
    kind: evidence.kind,
    level: evidence.level,
    correct: evidence.correct,
    transcript_available: evidence.transcript !== '',
    transcript: evidence.transcript,
    normalized_transcript: evidence.normalizedTranscript,
    transcript_similarity: evidence.transcriptSimilarity,
    phonetic_similarity: evidence.phoneticSimilarity,
    latency_ms: evidence.latencyMs,
    speech_detected: evidence.speechDetected,
    error_type: evidence.errorType ?? null,
    provider: resultProvider,
  };
}

export function speechFeaturesEventPayload(evidence: SpeechTrialEvidence): Record<string, unknown> {
  return {
    modality: 'speech',
    task_id: evidence.taskId,
    kind: evidence.kind,
    level: evidence.level,
    features: numericFeatures(evidence),
  };
}