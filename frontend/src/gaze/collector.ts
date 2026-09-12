import { FixationEngine } from './fixationEngine';
import { computeGazeFeatures } from './features';
import type { AoiRegion, EyeTrackingProvider, Fixation, GazeBatchPayload, GazeQuality, GazeSample, GazeTrialData, RegionRef } from './types';

const VIEWPORT_TOLERANCE = 10;

export function sanitizeCoordinates(x: number, y: number, viewportWidth: number, viewportHeight: number): boolean {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  if (x < 0 || y < 0) return false;
  if (x > viewportWidth + VIEWPORT_TOLERANCE || y > viewportHeight + VIEWPORT_TOLERANCE) return false;
  return true;
}

export function resolveRegion(x: number, y: number, regions: AoiRegion[]): RegionRef | null {
  for (const region of regions) {
    if (!region.available) continue;
    if (x >= region.left && x <= region.left + region.width && y >= region.top && y <= region.top + region.height) {
      return { type: region.type, label: region.label, elementId: region.elementId };
    }
  }
  return null;
}

export interface CollectorOptions {
  provider: EyeTrackingProvider;
  viewportWidth: number;
  viewportHeight: number;
  regions?: AoiRegion[];
  estimateNow?: () => number;
  onSampleStats?: (samples: number, aoiSamples: number) => void;
}

export class GazeCollector {
  private readonly samples: GazeSample[] = [];
  private readonly fixations: Fixation[] = [];
  private readonly engine: FixationEngine;
  private regions: AoiRegion[];
  private previousTimestampMs: number | null = null;
  private dropped = 0;
  private outOfOrder = 0;
  private aoiMatches = 0;
  private pendingRegions: AoiRegion[] = [];
  private estimateNow: () => number;

  constructor(private readonly options: CollectorOptions) {
    this.regions = options.regions ?? [];
    this.estimateNow = options.estimateNow ?? (() => Date.now());
    this.engine = new FixationEngine((x, y) => resolveRegion(x, y, this.regions));
  }

  aoiSampleCount(): number {
    return this.aoiMatches;
  }

  setRegions(regions: AoiRegion[]): void {
    this.regions = regions;
  }

  async start(): Promise<void> {
    this.samples.length = 0;
    this.fixations.length = 0;
    this.engine.reset();
    this.previousTimestampMs = null;
    this.dropped = 0;
    this.outOfOrder = 0;
    this.aoiMatches = 0;
    await this.options.provider.startTracking((x, y, confidence) => this.accept(x, y, confidence));
  }

  async stop(): Promise<void> {
    await this.options.provider.stopTracking();
  }

  ingest(x: number, y: number, confidence?: number): void {
    this.accept(x, y, confidence);
  }

  completeTrial(trialRef: string): GazeTrialData {
    const pending = this.engine.flush();
    if (pending) this.fixations.push(pending);
    const quality: GazeQuality = this.samples.length === 0 ? 'unavailable' : this.dropped > 0 || this.outOfOrder > 0 ? 'degraded' : 'tracking';
    const data: GazeTrialData = {
      trialRef,
      samples: [...this.samples],
      fixations: [...this.fixations],
      quality,
      features: computeGazeFeatures(this.samples.length, this.fixations),
    };
    this.samples.length = 0;
    this.fixations.length = 0;
    this.engine.reset();
    this.previousTimestampMs = null;
    this.dropped = 0;
    this.outOfOrder = 0;
    this.aoiMatches = 0;
    return data;
  }

  private accept(x: number, y: number, confidence?: number): void {
    if (!sanitizeCoordinates(x, y, this.options.viewportWidth, this.options.viewportHeight)) {
      this.dropped += 1;
      return;
    }
    const now = this.estimateNow();
    let quality: GazeQuality = 'tracking';
    if (this.previousTimestampMs !== null && now < this.previousTimestampMs) {
      quality = 'out_of_order';
      this.outOfOrder += 1;
    }
    this.previousTimestampMs = Math.max(this.previousTimestampMs ?? 0, now);
    const sample: GazeSample = {
      schemaVersion: '1.0',
      timestampMs: now,
      x,
      y,
      confidence,
      quality,
      viewportWidth: this.options.viewportWidth,
      viewportHeight: this.options.viewportHeight,
      provider: this.options.provider.name,
    };
    this.samples.push(sample);
    const fixation = this.engine.push(sample);
    if (fixation) this.fixations.push(fixation);
    if (resolveRegion(x, y, this.regions)) this.aoiMatches += 1;
    this.options.onSampleStats?.(this.samples.length, this.aoiMatches);
  }
}

export function toGazeBatchPayload(data: GazeTrialData, calibrationCompleted = false): GazeBatchPayload {
  return {
    provider: data.samples[0]?.provider ?? 'unknown',
    providerVersion: 'webgazer-1.0',
    quality: data.quality,
    schemaVersion: '1.0',
    samples: data.samples.map(sample => ({
      x: sample.x,
      y: sample.y,
      timestamp_ms: sample.timestampMs,
      confidence: sample.confidence,
      quality: sample.quality,
      viewport_width: sample.viewportWidth,
      viewport_height: sample.viewportHeight,
    })),
    fixations: data.fixations.map(fixation => ({
      start_timestamp_ms: fixation.startTime,
      end_timestamp_ms: fixation.endTime,
      duration_ms: fixation.durationMs,
      x: fixation.x,
      y: fixation.y,
      target_type: fixation.targetType,
      target_id: fixation.targetId,
    })),
    calibration_completed: calibrationCompleted,
  };
}