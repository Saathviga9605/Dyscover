import { describe, expect, it } from 'vitest';
import { assessmentPlan } from '.';

describe('assessment plan', () => {
  it('contains five versioned games with distinct domains', () => {
    expect(assessmentPlan).toHaveLength(5);
    expect(new Set(assessmentPlan.map(game => game.id)).size).toBe(5);
    assessmentPlan.forEach(game => expect(game.gameVersion).toBe('1.0.0'));
  });

  it('evaluates a correct trial without medical interpretation', () => {
    const game = assessmentPlan[0];
    const trial = game.createTrial({ index: 0, difficulty: 1, sessionId: 'test-session', random: { next: () => .1, int: () => 0, pick: <T>(items: T[]) => items[0], shuffle: <T>(items: T[]) => items } });
    const evaluation = game.evaluateResponse(trial, trial.expectedResponse);
    expect(evaluation.correct).toBe(true);
    expect(evaluation).not.toHaveProperty('probability');
  });
});
