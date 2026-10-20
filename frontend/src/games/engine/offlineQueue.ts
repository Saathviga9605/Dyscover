import type { AssessmentEvent, Trial } from './types';

export const QUEUE_KEY = 'dyscover-assessment-event-queue';
export const TRIAL_MAP_KEY = 'dyscover-backend-trial-id-map';
// Bounded so a long offline period cannot exhaust browser storage.
export const MAX_QUEUE_ITEMS = 500;

export type PersistedItem = {
  kind: 'trial' | 'event' | 'gaze' | 'speech_features' | 'speech_session';
  trialRef?: string;
  path: string;
  payload: Trial | AssessmentEvent | Record<string, unknown>;
  options?: RequestInit;
};

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or unavailable: the observation is lost rather than crashing the game.
  }
}

export function readQueue(): PersistedItem[] {
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) ?? '[]') as PersistedItem[];
  } catch {
    return [];
  }
}

export function enqueue(item: PersistedItem): void {
  const queue = readQueue();
  queue.push(item);
  write(QUEUE_KEY, queue.slice(-MAX_QUEUE_ITEMS));
}

export function clearQueue(): void {
  try {
    localStorage.removeItem(QUEUE_KEY);
    localStorage.removeItem(TRIAL_MAP_KEY);
  } catch {
    // ignore
  }
}

/** HTTP statuses that will never succeed on retry; such items are dropped. */
function isPermanentFailure(error: unknown): boolean {
  const status = (error as { status?: number } | null)?.status;
  return (
    typeof status === 'number' &&
    status >= 400 &&
    status < 500 &&
    status !== 401 &&
    status !== 408 &&
    status !== 429
  );
}

let flushing: Promise<void> | null = null;

/**
 * Send queued items in order. Stops at the first transient failure (network,
 * 5xx, auth, rate limit) so ordering is preserved; drops items the server
 * rejects permanently (e.g. 404 after a child was deleted, 409 on a completed
 * session) so one bad item cannot block the queue forever. Concurrent calls
 * share a single flush.
 */
export function flushQueue(send: (item: PersistedItem) => Promise<void>): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    let queue = readQueue();
    while (queue.length) {
      try {
        await send(queue[0]);
      } catch (error) {
        if (!isPermanentFailure(error)) break;
      }
      queue = readQueue().slice(1);
      write(QUEUE_KEY, queue);
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

export function readTrialIdMap(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(TRIAL_MAP_KEY) ?? '{}') as Record<string, string>;
  } catch {
    return {};
  }
}

export function updateTrialIdMap(localTrialId: string | undefined, backendTrialId: string): void {
  if (!localTrialId) return;
  const map = readTrialIdMap();
  map[localTrialId] = backendTrialId;
  write(TRIAL_MAP_KEY, map);
}
