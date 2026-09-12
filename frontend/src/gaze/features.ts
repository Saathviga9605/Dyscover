import type { Fixation } from './types';

const DISTRACTOR_LABELS = new Set(['target', 'distractor', 'option', 'instruction']);
const DEFAULT_REGION_LABELS = ['target', 'distractor', 'option', 'instruction'];
const JITTER_RADIUS = 40;

export function computeGazeFeatures(sampleCount: number, fixations: Fixation[], regionLabels: string[] = DEFAULT_REGION_LABELS): Record<string, number | null> {
  const ordered = [...fixations].sort((a, b) => a.startTime - b.startTime);
  const durations = ordered.map(exposure => exposure.durationMs);
  const count = ordered.length;
  const labeled = ordered.filter(exposure => exposure.targetType);

  const targetFixations = ordered.filter(exposure => exposure.targetType === 'target');
  const targetTime = targetFixations.length ? targetFixations.reduce((sum, exposure) => sum + exposure.durationMs, 0) : null;
  const distractorTime =
    count > 0
      ? ordered
          .filter(exposure => DISTRACTOR_LABELS.has(exposure.targetType ?? '') && exposure.targetType !== 'target')
          .reduce((sum, exposure) => sum + exposure.durationMs, 0)
      : null;

  const switches = count > 1 ? ordered.slice(1).reduce((sum, current, index) => sum + (ordered[index].targetType && current.targetType && ordered[index].targetType !== current.targetType ? 1 : 0), 0) : count === 1 ? 0 : null;
  const regressions =
    count > 1
      ? ordered.slice(1).reduce((sum, current, index) => sum + (current.x < ordered[index].x && Math.abs(current.y - ordered[index].y) <= JITTER_RADIUS ? 1 : 0), 0)
      : count === 1
        ? 0
        : null;

  const intervals = ordered.slice(1).map((current, index) => current.startTime - ordered[index].endTime).filter(value => value >= 0);
  const saccadeVariance = intervals.length < 2 ? null : populationVariance(intervals);

  const entropy = labeled.length < 2 ? null : computeEntropy(labeled.map(exposure => exposure.targetType ?? 'other'));

  const horizontal = ordered.slice(1).map((current, index) => current.x - ordered[index].x);
  const vertical = ordered.slice(1).map((current, index) => current.y - ordered[index].y);
  const magnitudes = horizontal.map((dx, index) => Math.hypot(dx, vertical[index]));
  const horizontalBias = count > 1 && magnitudes.length && magnitudes.reduce((sum, value) => sum + value, 0) > 0 ? horizontal.reduce((sum, dx) => sum + dx, 0) / magnitudes.reduce((sum, value) => sum + value, 0) : null;

  const present = new Set(labeled.map(exposure => exposure.targetType));
  const coverage = count > 0 && regionLabels.length ? (present.size ? (present.size - 0) / regionLabels.length : 0) : null;

  return {
    gaze_sample_count: sampleCount,
    gaze_fixation_count: count,
    gaze_mean_fixation_duration_ms: durations.length ? mean(durations) : null,
    gaze_max_fixation_duration_ms: durations.length ? Math.max(...durations) : null,
    gaze_target_fixation_time_ms: targetTime,
    gaze_distractor_fixation_time_ms: distractorTime,
    gaze_time_to_first_target_fixation_ms:
      targetFixations.length && ordered.length ? Math.round(Math.min(...targetFixations.map(exposure => exposure.startTime)) - ordered[0].startTime) : null,
    gaze_fixation_switch_count: switches,
    gaze_regression_count: regressions,
    gaze_saccade_variance_ms2: saccadeVariance,
    gaze_scanpath_entropy: entropy,
    gaze_horizontal_saccade_bias: horizontalBias,
    gaze_coverage_ratio: coverage,
  };
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function populationVariance(values: number[]): number {
  const average = mean(values);
  return values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length;
}

function computeEntropy(labels: string[]): number {
  const counts = new Map<string, number>();
  for (const label of labels) counts.set(label, (counts.get(label) ?? 0) + 1);
  const total = labels.length;
  let entropy = 0;
  for (const count of counts.values()) {
    const ratio = count / total;
    entropy -= ratio * Math.log2(ratio);
  }
  return entropy;
}