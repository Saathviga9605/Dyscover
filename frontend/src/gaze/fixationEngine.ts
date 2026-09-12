import type { Fixation, GazeSample, RegionRef } from './types';

const FIXATION_RADIUS = 40;
const FIXATION_MIN_DURATION_MS = 100;
const JITTER_RADIUS = 35;

type Resolver = (x: number, y: number) => RegionRef | null;

interface Cluster {
  x: number;
  y: number;
  count: number;
  first: GazeSample;
  last: GazeSample;
}

export class FixationEngine {
  private readonly radius: number;
  private readonly minDurationMs: number;
  private cluster: Cluster | null = null;

  constructor(private readonly resolveRegion: Resolver, radius = FIXATION_RADIUS, minDurationMs = FIXATION_MIN_DURATION_MS) {
    this.radius = radius;
    this.minDurationMs = minDurationMs;
  }

  push(sample: GazeSample): Fixation | null {
    if (!this.cluster) {
      this.cluster = { x: sample.x, y: sample.y, count: 1, first: sample, last: sample };
      return null;
    }
    const distance = Math.hypot(sample.x - this.cluster.x, sample.y - this.cluster.y);
    if (distance <= this.radius && Math.abs(sample.y - this.cluster.y) <= JITTER_RADIUS) {
      this.cluster.count += 1;
      this.cluster.x = this.cluster.x + (sample.x - this.cluster.x) / this.cluster.count;
      this.cluster.y = this.cluster.y + (sample.y - this.cluster.y) / this.cluster.count;
      this.cluster.last = sample;
      return null;
    }
    const completed = this.flush();
    this.cluster = { x: sample.x, y: sample.y, count: 1, first: sample, last: sample };
    return completed;
  }

  flush(): Fixation | null {
    const cluster = this.cluster;
    this.cluster = null;
    if (!cluster) return null;
    const durationMs = cluster.last.timestampMs - cluster.first.timestampMs;
    if (durationMs < this.minDurationMs) return null;
    const region = this.resolveRegion(cluster.x, cluster.y);
    const fixation: Fixation = {
      startTime: cluster.first.timestampMs,
      endTime: cluster.last.timestampMs,
      durationMs,
      x: Math.round(cluster.x * 10) / 10,
      y: Math.round(cluster.y * 10) / 10,
    };
    if (region) {
      fixation.targetType = region.type === 'neutral' ? 'other' : region.type;
      fixation.targetId = region.label;
    }
    return fixation;
  }

  reset(): void {
    this.cluster = null;
  }
}