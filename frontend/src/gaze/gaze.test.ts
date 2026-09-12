import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { captureRegions, regionForPoint } from './aoi';
import { FixationEngine } from './fixationEngine';
import { computeGazeFeatures } from './features';
import { GazeCollector, sanitizeCoordinates, toGazeBatchPayload, resolveRegion } from './collector';
import type { AoiRegion, EyeTrackingProvider, GazeSample } from './types';
import { browserSupportsEyeTrackingCapability, NoopEyeTrackingProvider } from './provider';
import { createEyeTrackingProvider } from './webgazerProvider';
import { useGazeTracking } from './useGazeTracking';

function fakeProvider(): EyeTrackingProvider & { samples: Array<[number, number, number]> } {
  const samples: Array<[number, number, number]> = [];
  return {
    name: 'test',
    version: '1.0',
    phase: 'READY',
    samples,
    setPhaseListener() {},
    async requestAccess() {
      return true;
    },
    async beginCalibration() {},
    async setCalibrationPoint() {},
    finishCalibration() {},
    async startTracking(onSample) {
      for (const [x, y, now] of samples.splice(0)) onSample(x, y, now);
    },
    async stopTracking() {},
    async cleanup() {},
  };
}

function samplePoint(x: number, y: number, t: number): GazeSample {
  return { schemaVersion: '1.0', timestampMs: t, x, y, quality: 'tracking', viewportWidth: 1280, viewportHeight: 720, provider: 'test' };
}

describe('gaze coordinate sanitization', () => {
  it('accepts coordinates inside the viewport', () => {
    expect(sanitizeCoordinates(50, 60, 1280, 720)).toBe(true);
  });

  it('rejects non-finite coordinates', () => {
    expect(sanitizeCoordinates(Number.NaN, 10, 1280, 720)).toBe(false);
    expect(sanitizeCoordinates(Infinity, 10, 1280, 720)).toBe(false);
  });

  it('rejects negative and out-of-bounds coordinates', () => {
    expect(sanitizeCoordinates(-1, 10, 1280, 720)).toBe(false);
    expect(sanitizeCoordinates(50, 800, 1280, 720)).toBe(false);
    expect(sanitizeCoordinates(2000, 10, 1280, 720)).toBe(false);
  });
});

describe('fixation engine', () => {
  it('merges samples inside the radius into a single fixation', () => {
    const engine = new FixationEngine(() => null, 40, 100);
    engine.push(samplePoint(10, 10, 0));
    engine.push(samplePoint(12, 10, 50));
    engine.push(samplePoint(10, 11, 120));
    const finished = engine.push(samplePoint(200, 100, 150));
    expect(finished).not.toBeNull();
    expect(finished!.durationMs).toBeGreaterThanOrEqual(100);
    expect(Math.abs(finished!.x - 10.7)).toBeLessThan(1);
  });

  it('filters fixations shorter than the minimum duration', () => {
    const engine = new FixationEngine(() => null, 40, 100);
    engine.push(samplePoint(10, 10, 0));
    const finished = engine.push(samplePoint(200, 10, 30));
    expect(finished).toBeNull();
  });

  it('classifies a fixation by the region under its centroid', () => {
    const regions: AoiRegion[] = [{ label: 'target', type: 'target', left: 0, top: 0, width: 100, height: 100, available: true }];
    const engine = new FixationEngine((x, y) => resolveRegion(x, y, regions), 40, 100);
    engine.push(samplePoint(50, 50, 0));
    engine.push(samplePoint(50, 51, 30));
    engine.push(samplePoint(50, 50, 60));
    engine.push(samplePoint(50, 50, 120));
    const finished = engine.push(samplePoint(500, 500, 150));
    expect(finished).not.toBeNull();
    expect(finished!.targetType).toBe('target');
    expect(finished!.targetId).toBe('target');
  });
});

describe('gaze feature extraction (deterministic, numeric)', () => {
  it('computes the canonical aggregate features', () => {
    const features = computeGazeFeatures(10, [
      { startTime: 0, endTime: 220, durationMs: 220, x: 100, y: 100, targetType: 'target', targetId: 'target' },
      { startTime: 300, endTime: 480, durationMs: 180, x: 400, y: 90, targetType: 'option', targetId: 'option' },
      { startTime: 600, endTime: 840, durationMs: 240, x: 100, y: 105, targetType: 'target', targetId: 'target' },
    ]);
    expect(features.gaze_sample_count).toBe(10);
    expect(features.gaze_fixation_count).toBe(3);
    expect(features.gaze_mean_fixation_duration_ms).toBeCloseTo((220 + 180 + 240) / 3, 3);
    expect(features.gaze_max_fixation_duration_ms).toBe(240);
    expect(features.gaze_target_fixation_time_ms).toBe(460);
    expect(features.gaze_distractor_fixation_time_ms).toBe(180);
    expect(features.gaze_fixation_switch_count).toBe(2);
    expect(features.gaze_coverage_ratio).toBeCloseTo(2 / 4, 3);
    expect(features.gaze_scanpath_entropy).toBeGreaterThan(0);
  });

  it('produces nulls (not scores) for missing timelines', () => {
    const features = computeGazeFeatures(0, []);
    expect(features.gaze_fixation_count).toBe(0);
    expect(features.gaze_mean_fixation_duration_ms).toBeNull();
    expect(features.gaze_scanpath_entropy).toBeNull();
    expect(features.gaze_saccade_variance_ms2).toBeNull();
  });
});

describe('gaze collector', () => {
  it('marks out-of-order samples and degrades quality', () => {
    const provider = fakeProvider();
    let now = 1000;
    const collector = new GazeCollector({ provider, viewportWidth: 1280, viewportHeight: 720, estimateNow: () => now });
    now = 1000;
    collector.ingest(10, 10);
    now = 800;
    collector.ingest(11, 11);
    const data = collector.completeTrial('t1');
    expect(data.samples.length).toBe(2);
    expect(data.samples.some(sample => sample.quality === 'out_of_order')).toBe(true);
    expect(data.quality).toBe('degraded');
  });

  it('drops invalid coordinates without recording them', () => {
    const provider = fakeProvider();
    const collector = new GazeCollector({ provider, viewportWidth: 1280, viewportHeight: 720, estimateNow: () => 5 });
    collector.ingest(50, 700);
    collector.ingest(Infinity, 10);
    collector.ingest(-1, 10);
    collector.ingest(60, 60);
    const data = collector.completeTrial('t1');
    expect(data.samples.length).toBe(2);
    expect(data.quality).toBe('degraded');
  });
});

describe('gaze batch payload is numeric-only (parent safe)', () => {
  it('never carries image, video, or raw blob data', () => {
    const provider = fakeProvider();
    const collector = new GazeCollector({ provider, viewportWidth: 1280, viewportHeight: 720, estimateNow: () => 5 });
    collector.ingest(100, 100);
    const data = collector.completeTrial('t1');
    const payload = toGazeBatchPayload(data);
    expect(payload.schemaVersion).toBe('1.0');
    expect(payload.quality).toBe('tracking');
    for (const sample of payload.samples) {
      expect(typeof sample.x).toBe('number');
      expect(typeof sample.y).toBe('number');
      expect(Number.isFinite(sample.x)).toBe(true);
      expect(Number.isFinite(sample.y)).toBe(true);
      expect(Array.isArray(sample.x)).toBe(false);
    }
    expect(payload.samples.every(sample => !('image' in sample) && !('raw' in sample) && !('blob' in sample))).toBe(true);
  });

  it('reports unavailable when no gaze was captured', () => {
    const provider = fakeProvider();
    const collector = new GazeCollector({ provider, viewportWidth: 1280, viewportHeight: 720 });
    const data = collector.completeTrial('t-empty');
    expect(data.quality).toBe('unavailable');
    expect(data.samples.length).toBe(0);
  });
});

describe('AOI capture and classification', () => {
  beforeEach(() => {
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const element = this as HTMLElement;
      const width = parseFloat(element.style.width) || 0;
      const height = parseFloat(element.style.height) || 0;
      return { left: 0, top: 0, width, height, right: width, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    document.body.innerHTML = '<div class="flash-stimulus" style="left:0;top:0;width:120px;height:80px">cat</div><button class="word-option" style="left:0;top:0;width:100px;height:50px">cat</button>';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('captures regions from the live game DOM', () => {
    const regions = captureRegions('word-flash', document);
    expect(regions.some(region => region.type === 'target' && region.available)).toBe(true);
    expect(regions.some(region => region.type === 'option')).toBe(true);
  });

  it('classifies a point into the correct region', () => {
    const regions = captureRegions('word-flash', document);
    const match = regionForPoint(10, 10, regions);
    expect(match?.type).toBe('target');
  });
});

describe('provider capability and fallback', () => {
  it('reports the secure-context camera requirement', () => {
    const secure = browserSupportsEyeTrackingCapability();
    expect(typeof secure).toBe('boolean');
  });

  it('noop provider is unavailable and never produces samples', async () => {
    const provider = new NoopEyeTrackingProvider();
    expect(await provider.requestAccess()).toBe(false);
    expect(provider.phase).toBe('UNAVAILABLE');
    await expect(provider.startTracking(() => undefined)).rejects.toThrow();
  });
});

describe('webgazer provider (stubbed script)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn(() => Promise.resolve({})) },
    });
    const webgazer = {
      params: {},
      setRegression: vi.fn(() => webgazer),
      setTracker: vi.fn(() => webgazer),
      addMouseEventListeners: vi.fn(() => webgazer),
      removeMouseEventListeners: vi.fn(() => webgazer),
      begin: vi.fn(() => Promise.resolve()),
      end: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      recordScreenPosition: vi.fn(() => webgazer),
      setGazeListener: vi.fn(() => webgazer),
      showVideo: vi.fn(() => webgazer),
      showPredictionPoints: vi.fn(() => webgazer),
      showFaceOverlay: vi.fn(() => webgazer),
      showFaceFeedbackBox: vi.fn(() => webgazer),
    } as unknown as Window['webgazer'];
    window.webgazer = webgazer;
  });

  afterEach(() => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
    delete (window as { webgazer?: unknown }).webgazer;
  });

  it('requests access, emits calibration points, and streams gaze samples', async () => {
    const provider = createEyeTrackingProvider();
    expect(await provider.requestAccess()).toBe(true);
    await provider.beginCalibration();
    await provider.setCalibrationPoint(100, 100);
    provider.finishCalibration();
    expect(provider.phase).toBe('READY');
    const onSample = vi.fn();
    await provider.startTracking(onSample);
    expect(provider.phase).toBe('TRACKING');
    const listener = (window.webgazer!.setGazeListener as ReturnType<typeof vi.fn>).mock.calls[0][0] as (data: { x: number; y: number }) => void;
    listener({ x: 12, y: 34 });
    expect(onSample).toHaveBeenCalledWith(12, 34);
    await provider.cleanup();
    expect(window.webgazer).toBeUndefined();
  });
});

describe('useGazeTracking consent and availability', () => {
  beforeEach(() => {
    window.localStorage.removeItem('dyscover-gaze-consent');
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
  });

  afterEach(() => {
    window.localStorage.removeItem('dyscover-gaze-consent');
  });

  it('is unavailable when the browser cannot access a camera', () => {
    const { result } = renderHook(() => useGazeTracking('word-flash'));
    expect(result.current.capable).toBe(false);
    expect(result.current.phase).toBe('UNAVAILABLE');
    expect(result.current.consented).toBe(false);
  });

  it('proceeds safely without gaze: begin/harvest are no-ops', async () => {
    const { result } = renderHook(() => useGazeTracking('word-flash'));
    await result.current.beginTrial('trial-a');
    const data = result.current.harvestTrial('trial-a');
    expect(data).toBeNull();
    expect(result.current.tracking).toBe(false);
  });
});

describe('calibration-completion path', () => {
  beforeEach(() => {
    window.localStorage.removeItem('dyscover-gaze-consent');
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [] })) },
    });
    const webgazer = {
      params: {},
      setRegression: vi.fn(() => webgazer),
      setTracker: vi.fn(() => webgazer),
      addMouseEventListeners: vi.fn(() => webgazer),
      removeMouseEventListeners: vi.fn(() => webgazer),
      begin: vi.fn(() => Promise.resolve()),
      end: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      recordScreenPosition: vi.fn(() => webgazer),
      setGazeListener: vi.fn(() => webgazer),
      showVideo: vi.fn(() => webgazer),
      showPredictionPoints: vi.fn(() => webgazer),
      showFaceOverlay: vi.fn(() => webgazer),
      showFaceFeedbackBox: vi.fn(() => webgazer),
    } as unknown as Window['webgazer'];
    window.webgazer = webgazer;
  });

  afterEach(() => {
    window.localStorage.removeItem('dyscover-gaze-consent');
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
    delete (window as { webgazer?: unknown }).webgazer;
  });

  it('enable() resolves CALIBRATING (so the overlay opens) and completed calibration marks the batch calibration_completed: true', async () => {
    const { result } = renderHook(() => useGazeTracking('word-flash'));
    const phase = await act(async () => result.current.enable());
    expect(phase).toBe('CALIBRATING');
    act(() => result.current.finalizeCalibration());
    expect(result.current.calibrationCompleted).toBe(true);
    await result.current.beginTrial('trial-1');
    const gazeListener = (window.webgazer!.setGazeListener as ReturnType<typeof vi.fn>).mock.calls[0][0] as (data: { x: number; y: number }) => void;
    gazeListener({ x: 60, y: 60 });
    const data = result.current.harvestTrial('trial-1');
    expect(data).not.toBeNull();
    const payload = toGazeBatchPayload(data!, result.current.calibrationCompleted);
    expect(payload.calibration_completed).toBe(true);
    void result.current.cleanup();
  });

  it('batches carry calibration_completed: false when calibration was never completed', async () => {
    const { result } = renderHook(() => useGazeTracking('word-flash'));
    await result.current.enable();
    await result.current.beginTrial('trial-2');
    const gazeListener = (window.webgazer!.setGazeListener as ReturnType<typeof vi.fn>).mock.calls[0][0] as (data: { x: number; y: number }) => void;
    gazeListener({ x: 60, y: 60 });
    const data = result.current.harvestTrial('trial-2');
    expect(data).not.toBeNull();
    const payload = toGazeBatchPayload(data!, result.current.calibrationCompleted);
    expect(payload.calibration_completed).toBe(false);
    void result.current.cleanup();
  });
});