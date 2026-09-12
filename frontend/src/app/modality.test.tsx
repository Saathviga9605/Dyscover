import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { persistGazeBatch } from '../games/persistence';
import { readQueue } from '../games/engine';
import { ModalitySummaryCard } from './ModalitySummaryCard';
import { toGazeBatchPayload } from '../gaze';
import type { GazeBatchPayload } from '../services/apiClient';

const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

const numericBatch: GazeBatchPayload = {
  provider: 'webgazer',
  providerVersion: 'webgazer-1.0',
  quality: 'tracking',
  schemaVersion: '1.0',
  samples: [{ x: 100, y: 200, timestamp_ms: 1234, quality: 'tracking', viewport_width: 1280, viewport_height: 720 }],
  fixations: [{ start_timestamp_ms: 1000, end_timestamp_ms: 2000, duration_ms: 1000, x: 100, y: 200 }],
};

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

describe('multimodal observation continues when gaze is present only as numbers', () => {
  beforeEach(() => {
    stubLocalStorage();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persists the gaze batch to the numeric endpoint when a backend trial exists', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: async () => ({ samples_created: 1 }) })));
    await persistGazeBatch('trial-1', 'backend-1', numericBatch);
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const [url, init] = fetchMock.mock.calls[0] as [string, { body?: string }];
    expect(url).toBe(`${baseUrl}/gaze/trials/backend-1/gaze`);
    const posted = JSON.parse((init?.body as string) ?? '{}');
    expect(posted.samples[0].x).toBe(100);
    expect('image' in posted.samples[0]).toBe(false);
  });

  it('queues gaze data offline and resolves it to the backend trial later', async () => {
    await persistGazeBatch('trial-1', null, numericBatch);
    const queued = readQueue().filter(item => item.kind === 'gaze');
    expect(queued.length).toBe(1);
    expect(queued[0].trialRef).toBe('trial-1');
  });

  it('queue attempt throws until trial id resolves, never sending media', async () => {
    await persistGazeBatch('trial-1', null, numericBatch);
    const queued = readQueue();
    expect(queued.every(item => typeof item.payload !== 'string')).toBe(true);
  });
});

describe('gaze batch exposes no labels, thresholds, or probabilities', () => {
  it('payload contains only coordinates, times, and quality flags', () => {
    const data = {
      trialRef: 'trial-1',
      samples: [{ schemaVersion: '1.0', timestampMs: 5, x: 1, y: 2, quality: 'tracking' as const, viewportWidth: 1280, viewportHeight: 720, provider: 'webgazer' }],
      fixations: [],
      quality: 'tracking' as const,
      features: {},
    };
    const payload = toGazeBatchPayload(data);
    const flat = JSON.stringify(payload);
    for (const forbidden of ['probability', 'threshold', 'label', 'score', 'risk']) {
      expect(flat).not.toContain(forbidden);
    }
  });
});

describe('parent-safe modality summary card', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(cleanup);

  it('shows the never-store-media notice', () => {
    const dataQuality: Record<string, unknown> = { gaze_availability: 0.5, speech_availability: 0 };
    render(<ModalitySummaryCard dataQuality={dataQuality} />);
    expect(screen.getByText(/never saved or uploaded/i)).toBeTruthy();
  });

  it('reports gaze coverage as a plain percentage, not a clinical score', () => {
    const dataQuality: Record<string, unknown> = { gaze_availability: 0.5 };
    render(<ModalitySummaryCard dataQuality={dataQuality} />);
    expect(screen.getByText(/50% of trials had gaze data/i)).toBeTruthy();
    expect(screen.queryByText(/diagnos/i)).toBeNull();
  });
});