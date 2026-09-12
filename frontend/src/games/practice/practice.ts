import { letterDetective, wordFlash, sequenceQuest, wordMaze } from '../definitions';
import type { GameDefinition, AssessmentEvent, Trial } from '../engine';

const PRACTICE_GAMES: Record<string, GameDefinition<any>> = {
  'symbol-match': letterDetective,
  'word-builder': wordFlash,
  'sequence-recall': sequenceQuest,
  'visual-search': wordMaze,
};

/** Map a remedial activity id to its supporting game definition (null if unknown). */
export function practiceGameFor(activityId: string): GameDefinition<Trial> | null {
  return PRACTICE_GAMES[activityId] ?? null;
}

/** Deterministic numeric seed derived from the practice session id. */
export function seedForSessionId(sessionId: string): number {
  const hex = sessionId.replace(/[^0-9a-fA-F]/g, '');
  const chunk = hex.slice(0, 8) || '0';
  return parseInt(chunk, 16) >>> 0;
}

/** Engine event types mirrored into persisted practice telemetry. */
export const MIRRORED_PRACTICE_EVENTS = new Set(['STIMULUS_SHOWN', 'RESPONSE_SUBMITTED', 'TRIAL_TIMEOUT', 'HINT_SHOWN']);

/** Canonical event types the practice endpoint accepts (subset of the shared contract). */
export const ALLOWED_PRACTICE_EVENTS = new Set(['SESSION_STARTED', 'SESSION_PAUSED', 'SESSION_RESUMED', 'STIMULUS_SHOWN', 'RESPONSE_SUBMITTED', 'TRIAL_TIMEOUT', 'HINT_SHOWN', 'SESSION_COMPLETED', 'SESSION_ABANDONED']);

export function toPracticeEvent(event: AssessmentEvent): { event_type: string; payload: Record<string, unknown> } {
  return { event_type: event.eventType, payload: event.payload as Record<string, unknown> };
}