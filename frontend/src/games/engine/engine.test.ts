import { describe, expect, it } from 'vitest';
import { letterDetective } from '../definitions/letterDetective';
import { GameEngine } from './engine';

describe('GameEngine', () => {
  it('creates reproducible trials and ordered events', () => {
    const first = new GameEngine(letterDetective, undefined, 12345);
    const second = new GameEngine(letterDetective, undefined, 12345);
    first.start(); second.start();
    const firstTrial = first.beginTrial();
    const secondTrial = second.beginTrial();
    expect(firstTrial.stimulus).toEqual(secondTrial.stimulus);
    first.recordResponse(firstTrial, firstTrial.expectedResponse);
    first.completeTrial(firstTrial);
    expect(first.events.map(event => event.sequenceNumber)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(firstTrial.correct).toBe(true);
  });

  it('pauses and resumes without changing the trial', () => {
    const engine = new GameEngine(letterDetective, undefined, 8);
    engine.start();
    const trial = engine.beginTrial();
    engine.pause();
    expect(engine.session.status).toBe('PAUSED');
    engine.resume();
    expect(engine.session.status).toBe('IN_PROGRESS');
    expect(engine.trials[0].trialId).toBe(trial.trialId);
  });
});
