import { describe, expect, it } from 'vitest';
import { ALLOWED_PRACTICE_EVENTS, MIRRORED_PRACTICE_EVENTS, practiceGameFor, seedForSessionId, toPracticeEvent } from './practice';
import { PRACTICE_COPY } from './practiceCopy';

describe('practice activity mapping', () => {
  it('maps every remedial activity to its supporting game definition', () => {
    expect(practiceGameFor('symbol-match')?.id).toBe('letter-detective');
    expect(practiceGameFor('word-builder')?.id).toBe('word-flash');
    expect(practiceGameFor('sequence-recall')?.id).toBe('sequence-quest');
    expect(practiceGameFor('visual-search')?.id).toBe('word-maze');
  });

  it('returns null for unknown activities instead of crashing', () => {
    expect(practiceGameFor('no-such-activity')).toBeNull();
  });
});

describe('practice seeding', () => {
  it('is deterministic for a given session id', () => {
    expect(seedForSessionId('abc123')).toBe(seedForSessionId('abc123'));
  });

  it('produces distinct seeds for distinct session ids', () => {
    expect(seedForSessionId('abcdef01')).not.toBe(seedForSessionId('abcdef02'));
  });
});

describe('practice event contract mapping', () => {
  it('mirrors only canonical events allowed by the practice endpoint', () => {
    expect(MIRRORED_PRACTICE_EVENTS.size).toBeGreaterThan(0);
    for (const eventType of MIRRORED_PRACTICE_EVENTS) {
      expect(ALLOWED_PRACTICE_EVENTS.has(eventType)).toBe(true);
    }
  });

  it('maps an engine event to the wire payload shape', () => {
    const event = toPracticeEvent({ eventType: 'RESPONSE_SUBMITTED', payload: { correct: true } } as never);
    expect(event).toEqual({ event_type: 'RESPONSE_SUBMITTED', payload: { correct: true } });
  });
});

describe('practice copy is encouragement-led and non-clinical', () => {
  const prohibited = ['dyslex', 'diagnos', 'disorder', 'deficit', 'severity', 'probab', 'risk', 'impair', 'treat', 'score'];

  it('contains no diagnostic, risk, or performance-judgement language', () => {
    const texts = Object.values(PRACTICE_COPY);
    for (const text of texts) {
      const lowered = text.toLowerCase();
      for (const word of prohibited) {
        expect(lowered).not.toContain(word);
      }
    }
  });
});