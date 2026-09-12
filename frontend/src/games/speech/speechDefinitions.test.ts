import { describe, expect, it } from 'vitest';
import { createSeededRandom } from '../engine';
import { letterBubblePop, mazeRunnerRush, soundQuestAdventure, type SpeechResponseRecord } from './speechDefinitions';

function wordResponse(transcript: string, overrides: Partial<SpeechResponseRecord> = {}): SpeechResponseRecord {
  return { transcript, confidence: 0.9, latencyMs: 1200, durationMs: 1500, speechDetected: Boolean(transcript), errorType: undefined, retriedNoSpeech: 0, ...overrides };
}

const plans = [soundQuestAdventure, letterBubblePop, mazeRunnerRush];

describe('speech game definitions', () => {
  it('maps each game to the planned assessment domain', () => {
    expect(soundQuestAdventure.domain).toBe('phonological-awareness');
    expect(letterBubblePop.domain).toBe('reading-fluency');
    expect(mazeRunnerRush.domain).toBe('attention-visual-search');
  });

  it('derives total trials from the per-level minimums', () => {
    expect(soundQuestAdventure.totalTrials).toBe(17);
    expect(letterBubblePop.totalTrials).toBe(14);
    expect(mazeRunnerRush.totalTrials).toBe(18);
  });

  it('creates trials that carry level-based difficulty and content', () => {
    const trial = soundQuestAdventure.createTrial({ index: 0, difficulty: 1, random: createSeededRandom(7), sessionId: 's1' });
    expect(trial.difficulty).toBe(1);
    expect(trial.stimulus.promptText).toBe('cat');
    expect(trial.stimulus.taskId).toBe('sound-quest-adventure:1:1');
    expect(trial.metadata.modality).toBe('speech');
  });

  it('assigns letter prompts to bubble pop level 2 pairs', () => {
    const trial = letterBubblePop.createTrial({ index: 4, difficulty: 2, random: createSeededRandom(3), sessionId: 's1' });
    expect(trial.difficulty).toBe(2);
    expect(trial.stimulus.kind).toBe('letter-pair');
  });

  it('evaluates a correct word response into evidence and features', () => {
    const trial = soundQuestAdventure.createTrial({ index: 0, difficulty: 1, random: createSeededRandom(7), sessionId: 's1' });
    const evaluation = soundQuestAdventure.evaluateResponse(trial, wordResponse('cat'));
    expect(evaluation.correct).toBe(true);
    const metadata = evaluation.metadata as { evidence: { taskId: string }; features: Record<string, number> };
    expect(metadata.evidence.taskId).toBe('sound-quest-adventure:1:1');
    expect(metadata.features.speech_transcript_similarity).toBe(1);
    expect(metadata.features.stimulus_difficulty).toBe(1);
  });

  it('gives no transcript similarity for an empty answer', () => {
    const trial = soundQuestAdventure.createTrial({ index: 0, difficulty: 1, random: createSeededRandom(7), sessionId: 's1' });
    const evaluation = soundQuestAdventure.evaluateResponse(trial, wordResponse('', { errorType: 'no-speech' }));
    expect(evaluation.correct).toBe(false);
    const metadata = evaluation.metadata as { evidence: { transcript: string } };
    expect(metadata.evidence.transcript).toBe('');
  });

  it('keeps the numeric features free of labels and probabilities', () => {
    const trial = soundQuestAdventure.createTrial({ index: 0, difficulty: 1, random: createSeededRandom(7), sessionId: 's1' });
    const metadata = soundQuestAdventure.evaluateResponse(trial, wordResponse('cat')).metadata as { features: Record<string, number> };
    for (const value of Object.values(metadata.features)) {
      expect(typeof value).toBe('number');
      expect(Number.isFinite(value)).toBe(true);
    }
    expect(metadata.features.speech_error_rate).toBeUndefined();
  });

  it('moves difficulty through the three levels', () => {
    const trial = mazeRunnerRush.createTrial({ index: 12, difficulty: 3, random: createSeededRandom(1), sessionId: 's1' });
    expect(trial.difficulty).toBe(3);
    expect(trial.stimulus.kind).toBe('word');
  });

  it('exposes a launchable plan of three games', () => {
    for (const def of plans) {
      expect(def.instructions.length).toBeGreaterThan(0);
      expect(def.estimatedDurationMinutes).toBeGreaterThan(0);
    }
  });
});