import type { AssessmentEvent, Trial } from './types';

const queueKey = 'dyscover-assessment-event-queue';
export type PersistedItem = { kind: 'trial' | 'event'; payload: Trial | AssessmentEvent; path: string; options?: RequestInit };

export function readQueue(): PersistedItem[] { try { return JSON.parse(localStorage.getItem(queueKey) ?? '[]') as PersistedItem[]; } catch { return []; } }
export function enqueue(item: PersistedItem): void { const queue = readQueue(); queue.push(item); localStorage.setItem(queueKey, JSON.stringify(queue)); }
export function removeFirst(): void { const queue = readQueue(); queue.shift(); localStorage.setItem(queueKey, JSON.stringify(queue)); }
export async function flushQueue(send: (item: PersistedItem) => Promise<void>): Promise<void> { for (const item of readQueue()) { try { await send(item); removeFirst(); } catch { break; } } }
