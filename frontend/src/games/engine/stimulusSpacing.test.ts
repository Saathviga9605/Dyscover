import { describe, expect, it, beforeEach } from 'vitest';
import type { GameDefinition, Trial } from './types';
import { GameEngine } from './engine';
import { StimulusSpacing, stimulusSignature } from './stimulusSpacing';

interface PoolStimulus { item: string; }

function trialFrom(item: string): Trial {
  return {
    trialId: `t_${item}_${Math.random()}`,
    sessionId: 's',
    gameId: 'pool-game',
    gameVersion: '1.0.0',
    trialIndex: 0,
    domain: 'visual-symbol-discrimination',
    difficulty: 1,
    startedAt: new Date().toISOString(),
    stimulus: { item },
    expectedResponse: 'x',
    score: 0,
    attemptCount: 0,
    errorCount: 0,
    metadata: {},
  };
}

function poolDefinition(pool: string[]): GameDefinition<Trial> {
  return {
    id: 'pool-game',
    name: 'Pool Game',
    description: '',
    domain: 'visual-symbol-discrimination',
    gameVersion: '1.0.0',
    ageRange: [5, 12],
    estimatedDurationMinutes: 2,
    difficultyLevels: [1, 2, 3, 4, 5],
    instructions: [],
    totalTrials: 10,
    createTrial: ({ random }) => trialFrom(random.pick(pool) as string),
    evaluateResponse: () => ({ correct: true, score: 1, actualResponse: null }),
    getNextDifficulty: () => 1,
  };
}

describe('StimulusSpacing', () => {
  it('detects recent stimuli and allows spaced reappearance', () => {
    const spacing = new StimulusSpacing(2, 6);
    spacing.push({ item: 'a' }, 'g');
    expect(spacing.isRecent({ item: 'a' }, 'g')).toBe(true);
    spacing.push({ item: 'b' }, 'g');
    spacing.push({ item: 'c' }, 'g');
    // 'a' has rolled out of the window of 2.
    expect(spacing.isRecent({ item: 'a' }, 'g')).toBe(false);
  });

  it('treats identical stimuli as equal and different stimuli as distinct', () => {
    expect(stimulusSignature({ item: 'a' }, 'g')).toBe(stimulusSignature({ item: 'a' }, 'g'));
    expect(stimulusSignature({ item: 'a' }, 'g')).not.toBe(stimulusSignature({ item: 'b' }, 'g'));
  });

  it('disables itself with a zero window', () => {
    const spacing = new StimulusSpacing(0, 6);
    spacing.push({ item: 'a' }, 'g');
    expect(spacing.isRecent({ item: 'a' }, 'g')).toBe(false);
    expect(spacing.retryLimit()).toBe(0);
  });
});

describe('GameEngine stimulus uniqueness', () => {
  let calls = 0;
  beforeEach(() => { calls = 0; });

  it('regenerates immediately-repeated stimuli without repeating in the recent window', () => {
    const base = poolDefinition(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']);
    const definition = { ...base, createTrial: (input: { index: number; difficulty: number; random: { pick<T>(items: T[]): T }; sessionId: string }) => { calls += 1; return base.createTrial(input as never); } };
    const engine = new GameEngine(definition, undefined, 7);
    engine.start();
    const trials = Array.from({ length: 8 }, () => engine.beginTrial());
    const items = trials.map(trial => (trial.stimulus as PoolStimulus).item);
    // The retry loop must actually run for at least one trial…
    expect(calls).toBeGreaterThan(trials.length);
    // …and no two stimuli within a sliding window of 4 trials may match.
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < Math.min(items.length, i + 4); j += 1) {
        expect(items[i]).not.toBe(items[j]);
      }
    }
  });

  it('remains deterministic when avoiding repeats', () => {
    const pool = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const first = new GameEngine(poolDefinition(pool), undefined, 99);
    const second = new GameEngine(poolDefinition(pool), undefined, 99);
    first.start(); second.start();
    const trials = Array.from({ length: 6 }, () => first.beginTrial());
    const replay = Array.from({ length: 6 }, () => second.beginTrial());
    expect(trials.map(t => (t.stimulus as PoolStimulus).item)).toEqual(replay.map(t => (t.stimulus as PoolStimulus).item));
  });
});