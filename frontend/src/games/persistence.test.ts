import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushAssessmentQueue, persistEvent, persistTrial } from './persistence';
import { enqueue, readQueue, readTrialIdMap } from './engine';
import type { AssessmentEvent, Trial } from './engine';

const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

function stubLocalStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => { store.set(key, value); },
    removeItem: (key: string) => { store.delete(key); },
    clear: () => { store.clear(); },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() { return store.size; },
  });
}

const trialPayload: Trial = {
  trialId: 'word-maze_trial_1_abc',
  sessionId: 'assessment-uuid',
  gameId: 'word-maze',
  gameVersion: '1.0.0',
  trialIndex: 0,
  domain: 'attention-visual-search',
  difficulty: 2,
  startedAt: '2026-01-01T12:00:00.000Z',
  stimulus: { size: 3, grid: [['c', 'a', 't']], targets: ['cat'], paths: {} },
  expectedResponse: ['cat'],
  actualResponse: ['cat'],
  correct: true,
  score: 1,
  reactionTimeMs: 842,
  attemptCount: 1,
  errorCount: 0,
  metadata: {},
  completedAt: '2026-01-01T12:00:05.000Z',
};

const eventPayload: AssessmentEvent = {
  eventId: 'event_1',
  sessionId: 'assessment-uuid',
  trialId: 'word-maze_trial_1_abc',
  gameId: 'word-maze',
  timestamp: '2026-01-01T12:00:04.000Z',
  performanceTime: 842.5,
  eventType: 'TRIAL_STARTED',
  sequenceNumber: 1,
  payload: {},
  schemaVersion: '2.0',
};

describe('telemetry persistence', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubLocalStorage();
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persistTrial returns the backend trial UUID and records the local-to-backend mapping online', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/trials')) return { ok: true, status: 201, json: async () => ({ id: 'backend-uuid-1', trial_number: 1 }) };
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    }));
    const backendId = await persistTrial('assessment-uuid', 'word-maze', trialPayload);
    expect(backendId).toBe('backend-uuid-1');
    expect(readTrialIdMap()['word-maze_trial_1_abc']).toBe('backend-uuid-1');
    expect(readQueue()).toEqual([]);
  });

  it('persistEvent enqueues the event with its local trial reference when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { return { ok: false, status: 502, json: async () => ({ detail: 'Bad gateway' }) }; }));
    await persistEvent('word-maze_trial_1_abc', eventPayload);
    const queue = readQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0]).toMatchObject({ kind: 'event', trialRef: 'word-maze_trial_1_abc' });
  });

  it('flushAssessmentQueue creates the queued trial first, then posts its events to the remapped backend UUID', async () => {
    enqueue({ kind: 'trial', trialRef: 'word-maze_trial_1_abc', path: '/assessments/assessment-uuid/games/word-maze/trials', payload: { trial_number: 1 } });
    enqueue({ kind: 'event', trialRef: 'word-maze_trial_1_abc', path: '/trials/word-maze_trial_1_abc/events', payload: { event_type: 'TRIAL_STARTED' } });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/trials') && url.includes('assessment-uuid')) return { ok: true, status: 201, json: async () => ({ id: 'backend-uuid-7' }) };
      if (url.includes('/trials/backend-uuid-7/events')) return { ok: true, status: 201, json: async () => ({ id: 'event-1' }) };
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    });
    vi.stubGlobal('fetch', fetchMock);

    await flushAssessmentQueue();

    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls[0]).toBe(`${baseUrl}/assessments/assessment-uuid/games/word-maze/trials`);
    expect(urls).toContain(`${baseUrl}/trials/backend-uuid-7/events`);
    expect(readQueue()).toEqual([]);
    expect(readTrialIdMap()['word-maze_trial_1_abc']).toBe('backend-uuid-7');
  });
});