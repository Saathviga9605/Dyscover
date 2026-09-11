import { describe, expect, it } from 'vitest';
import type { GameDefinition, Trial } from './types';
import { GameEngine } from './engine';
import { DifficultyManager } from './difficulty';

function def(): GameDefinition<Trial> {
  return {
    id: 'd-game',
    name: '',
    description: '',
    domain: 'visual-symbol-discrimination',
    gameVersion: '1.0.0',
    ageRange: [5, 12],
    estimatedDurationMinutes: 2,
    difficultyLevels: [1, 2, 3, 4, 5],
    instructions: [],
    totalTrials: 10,
    createTrial: ({ index, difficulty, sessionId }) => ({
      trialId: `t_${index}_${sessionId}`,
      sessionId,
      gameId: 'd-game',
      gameVersion: '1.0.0',
      trialIndex: index,
      domain: 'visual-symbol-discrimination',
      difficulty,
      startedAt: new Date().toISOString(),
      stimulus: { item: `s_${index}` },
      expectedResponse: 'x',
      score: 0,
      attemptCount: 0,
      errorCount: 0,
      metadata: {},
    }),
    evaluateResponse: () => ({ correct: true, score: 1, actualResponse: null }),
    getNextDifficulty: () => 1,
  };
}

function play(engine: GameEngine<Trial>, rounds: number, response: 'correct' | 'slow' = 'correct'): void {
  for (let i = 0; i < rounds; i += 1) {
    const trial = engine.beginTrial(i);
    const result = response === 'correct' ? { correct: true, score: 1, actualResponse: 'x', metadata: {} } : { correct: false, score: 0, actualResponse: 'x', metadata: {} };
    const updated = engine.recordResponse(trial, 'x', result);
    engine.completeTrial(updated);
  }
}

describe('DifficultyManager starting seed', () => {
  it('starts at the game minimum by default', () => {
    const engine = new GameEngine(def(), undefined, 1);
    expect(engine.beginTrial(0).difficulty).toBe(1);
    expect(new DifficultyManager().next([])).toBe(1);
  });
  it('uses the personalized starting level', () => {
    const engine = new GameEngine(def(), undefined, 1, 3);
    expect(engine.beginTrial(0).difficulty).toBe(3);
  });
  it('clamps a personalized starting level to the supported range', () => {
    expect(new DifficultyManager(1, 5, 9).next([])).toBe(5);
    expect(new DifficultyManager(1, 5, -2).next([])).toBe(1);
  });
  it('still adapts around the personalized starting level once enough history exists', () => {
    const manager = new DifficultyManager(1, 5, 2);
    const trial = (difficulty: number): Trial => ({ trialId: 't', sessionId: 's', gameId: 'd-game', gameVersion: '1.0.0', trialIndex: 0, domain: 'visual-symbol-discrimination', difficulty, startedAt: new Date().toISOString(), stimulus: { item: 'x' }, expectedResponse: 'x', score: 1, attemptCount: 1, errorCount: 0, correct: true, reactionTimeMs: 2000, metadata: {} });
    expect(manager.next([])).toBe(2);
    // Three strong, well-timed attempts step from the seeded level, not from the minimum.
    expect(manager.next([trial(2), trial(2), trial(2)])).toBe(3);
  });
});