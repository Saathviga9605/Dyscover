import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type DifficultyDecision } from './apiClient';
import { clampDifficulty, fetchRecommendedDifficulty, progressMessage, recommendationLabel, shouldApplyDifficulty, } from './childPersonalization';

const levels = [1, 2, 3, 4, 5];
const decision = (over: Partial<DifficultyDecision> = {}): DifficultyDecision => ({ level: 1, previous_level: null, default: 1, window_size: 3, reason: 'observed', changed: false, ...over });

afterEach(() => { vi.restoreAllMocks(); });

describe('clampDifficulty', () => {
  it('accepts a level the game supports', () => {
    expect(clampDifficulty(3, levels)).toBe(3);
  });
  it('rejects a level the game cannot express (falls back to the default)', () => {
    expect(clampDifficulty(99, levels)).toBeUndefined();
    expect(clampDifficulty(0, levels)).toBeUndefined();
  });
  it('rejects non-finite or unsupported level lists', () => {
    expect(clampDifficulty(NaN, levels)).toBeUndefined();
    expect(clampDifficulty(3, [])).toBeUndefined();
  });
});

describe('fetchRecommendedDifficulty', () => {
  const game = { id: 'letter-detective', difficultyLevels: levels };

  it('uses a personalized level when the API provides one', async () => {
    vi.spyOn(api, 'getPersonalizationDifficulty').mockResolvedValue(decision({ level: 3, changed: true }));
    await expect(fetchRecommendedDifficulty('child-1', game)).resolves.toBe(3);
  });

  it('falls back to the default when evidence is insufficient (level equals the default)', async () => {
    vi.spyOn(api, 'getPersonalizationDifficulty').mockResolvedValue(decision({ level: 1, changed: false }));
    await expect(fetchRecommendedDifficulty('child-1', game)).resolves.toBe(1);
  });

  it('never blocks gameplay when the API fails', async () => {
    vi.spyOn(api, 'getPersonalizationDifficulty').mockRejectedValue(new Error('offline'));
    await expect(fetchRecommendedDifficulty('child-1', game)).resolves.toBeUndefined();
  });

  it('does nothing without a known child id', async () => {
    const spy = vi.spyOn(api, 'getPersonalizationDifficulty');
    await expect(fetchRecommendedDifficulty(null, game)).resolves.toBeUndefined();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe('shouldApplyDifficulty', () => {
  it('applies an override only to a not-yet-started engine with no trials', () => {
    expect(shouldApplyDifficulty({ session: { status: 'NOT_STARTED' }, trials: [] })).toBe(true);
    expect(shouldApplyDifficulty({ session: { status: 'IN_PROGRESS' }, trials: [] })).toBe(false);
    expect(shouldApplyDifficulty({ session: { status: 'NOT_STARTED' }, trials: [{}] })).toBe(false);
    expect(shouldApplyDifficulty(null)).toBe(false);
  });
});

describe('progressMessage', () => {
  it('asks for another screening after exactly one screening (no false trend)', () => {
    expect(progressMessage({ child_id: 'c', engine_version: '1.0', mode: 'DETERMINISTIC_OBSERVATION', points: [{ assessment_id: 'a1', domains: {} }], comparison: null, note: null })).toBe('Complete another screening to see activity progress over time.');
  });
  it('invites the first screening when none exists', () => {
    expect(progressMessage({ child_id: 'c', engine_version: '1.0', mode: 'DETERMINISTIC_OBSERVATION', points: [], comparison: null, note: null })).toBe('Complete a screening to see activity progress over time.');
  });
  it('explains that two screenings are not yet enough to compare', () => {
    expect(progressMessage({ child_id: 'c', engine_version: '1.0', mode: 'DETERMINISTIC_OBSERVATION', points: [{ assessment_id: 'a1', domains: {} }, { assessment_id: 'a2', domains: {} }], comparison: null, note: null })).toBe('Not enough completed activity across screenings for a comparison yet.');
  });
  it('returns null so the dashboard renders the comparison when it exists', () => {
    expect(progressMessage({ child_id: 'c', engine_version: '1.0', mode: 'DETERMINISTIC_OBSERVATION', points: [{ assessment_id: 'a1', domains: { visual_symbol: .5 } }, { assessment_id: 'a2', domains: { visual_symbol: .7 } }], comparison: { earliest_assessment_id: 'a1', latest_assessment_id: 'a2', domains: { visual_symbol: { earliest_accuracy: .5, latest_accuracy: .7, delta: .2 } } }, note: null })).toBeNull();
  });
});

describe('recommendationLabel', () => {
  it('prefers the parent-friendly domain label', () => {
    expect(recommendationLabel({ game_id: 'letter-detective', target_domain: 'visual-symbol-discrimination', target_domain_label: 'Letter & symbol recognition', priority: 30, reason: 'r', category: 'practice_opportunity', kind: 'game_activity' })).toBe('Letter & symbol recognition');
  });
  it('never leaks the internal domain identifier when the label is missing', () => {
    expect(recommendationLabel({ game_id: 'letter-detective', target_domain: 'visual-symbol-discrimination', target_domain_label: null, priority: 30, reason: 'r', category: 'practice_opportunity', kind: 'game_activity' })).toBe('Activity');
  });
});