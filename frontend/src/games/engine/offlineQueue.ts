import type { AssessmentEvent, Trial } from './types';

const queueKey = 'dyscover-assessment-event-queue';
const trialMapKey = 'dyscover-backend-trial-id-map';

export type PersistedItem = { kind: 'trial' | 'event' | 'gaze' | 'speech_features'; trialRef?: string; path: string; payload: Trial | AssessmentEvent | Record<string, unknown>; options?: RequestInit };

export function readQueue(): PersistedItem[] { try { return JSON.parse(localStorage.getItem(queueKey) ?? '[]') as PersistedItem[]; } catch { return []; } }
export function enqueue(item: PersistedItem): void { const queue = readQueue(); queue.push(item); localStorage.setItem(queueKey, JSON.stringify(queue)); }
export function removeFirst(): void { const queue = readQueue(); queue.shift(); localStorage.setItem(queueKey, JSON.stringify(queue)); }
export async function flushQueue(send: (item: PersistedItem) => Promise<void>): Promise<void> { for (const item of readQueue()) { try { await send(item); removeFirst(); } catch { break; } } }

export function readTrialIdMap(): Record<string, string> { try { return JSON.parse(localStorage.getItem(trialMapKey) ?? '{}') as Record<string, string>; } catch { return {}; } }
export function updateTrialIdMap(localTrialId: string | undefined, backendTrialId: string): void {
  if (!localTrialId) return;
  const map = readTrialIdMap();
  map[localTrialId] = backendTrialId;
  localStorage.setItem(trialMapKey, JSON.stringify(map));
}