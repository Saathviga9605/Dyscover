import type { AssessmentDomain } from '../../types/assessment';
import type { GameDefinition, Trial, TrialEvaluation } from '../engine';
import { gradeFromRecognition } from './speechMatching';
import { buildSpeechEvidence, numericFeatures, responseSubmittedPayload, speechFeaturesEventPayload, type SpeechTrialEvidence } from './speechTelemetry';
import type { SpeechRecognitionResult } from './speechRecognition';
import { LETTER_BUBBLE_POP, MAZE_RUNNER_RUSH, SOUND_QUEST_ADVENTURE, type SpeechGameContent, type SpeechLevel, type SpeechPromptKind } from './speechGameContent';

export interface SpeechTrial extends Trial {
  stimulus: {
    promptText: string;
    kind: SpeechPromptKind;
    level: number;
    levelName: string;
    levelSubtitle: string;
    instructions: string[];
    taskId: string;
    hideAfterMs?: number;
    totalTimeMs?: number;
    distractionMode?: boolean;
    flashMode?: boolean;
    storyParts?: string[];
  };
  expectedResponse: string;
  actualResponse?: string | null;
  metadata: Record<string, unknown> & { modality: 'speech'; evidence?: SpeechTrialEvidence; features?: Record<string, number> };
}

export interface SpeechTrialInput {
  index: number;
  difficulty: number;
  random: import('../engine').SeededRandom;
  sessionId: string;
}

export type SpeechResponseRecord = Pick<SpeechRecognitionResult, 'transcript' | 'confidence' | 'latencyMs' | 'durationMs' | 'speechDetected' | 'errorType' | 'retriedNoSpeech'> & { provider?: string };

const LEVEL_COUNTS: Record<string, readonly number[]> = {
  'sound-quest-adventure': [6, 6, 5],
  'letter-bubble-pop': [4, 4, 6],
  'maze-runner-rush': [6, 6, 6],
};

function levelFor(game: SpeechGameContent, index: number): SpeechLevel {
  const counts = LEVEL_COUNTS[game.id] ?? game.levels.map(level => level.minTrials);
  let start = 0;
  for (let l = 0; l < game.levels.length; l += 1) {
    if (index < start + counts[l]!) return game.levels[l]!;
    start += counts[l]!;
  }
  return game.levels[game.levels.length - 1]!;
}

function promptFor(game: SpeechGameContent, level: SpeechLevel, index: number): string {
  const counts = LEVEL_COUNTS[game.id] ?? game.levels.map(item => item.minTrials);
  let start = 0;
  for (const count of counts) {
    if (index < start + count) break;
    start += count;
  }
  const pool = level.pool;
  return pool[(index - start) % pool.length] ?? pool[0]!;
}

function createTrialFactory(game: SpeechGameContent): GameDefinition<SpeechTrial>['createTrial'] {
  return ({ index, difficulty, random }: SpeechTrialInput) => {
    const level = levelFor(game, index);
    const promptText = promptFor(game, level, index);
    const levelIndex = game.levels.indexOf(level);
    return {
      trialId: `speech_${game.id}_${index}_${random.int(0, 99999)}`,
      sessionId: '',
      gameId: game.id,
      gameVersion: '3.0.0',
      trialIndex: index,
      domain: DOMAIN_BY_GAME[game.id],
      difficulty: levelIndex + 1,
      startedAt: new Date().toISOString(),
      stimulus: {
        promptText,
        kind: level.kind,
        level: levelIndex + 1,
        levelName: level.name,
        levelSubtitle: level.subtitle,
        instructions: [level.name, level.subtitle],
        taskId: `${game.id}:${levelIndex + 1}:${index + 1}`,
        hideAfterMs: level.hideAfterMs,
        totalTimeMs: level.totalTimeMs,
        distractionMode: level.distractionMode,
        flashMode: level.flashMode,
        storyParts: level.storyParts ? [...level.storyParts] : undefined,
      },
      expectedResponse: promptText,
      attemptCount: 0,
      errorCount: 0,
      score: 0,
      metadata: { modality: 'speech' },
    };
  };
}

function evaluateSpeechTrial(trial: SpeechTrial, response: SpeechResponseRecord): TrialEvaluation {
  const stimulus = trial.stimulus;
  const grade = gradeFromRecognition(stimulus.promptText, stimulus.kind, {
    transcript: response.transcript ?? '',
    confidence: response.confidence ?? 0,
    latencyMs: response.latencyMs ?? 0,
    durationMs: response.durationMs ?? 0,
    speechDetected: response.speechDetected ?? false,
    retriedNoSpeech: response.retriedNoSpeech ?? 0,
    provider: response.provider,
    errorType: response.errorType,
  } as SpeechRecognitionResult);

  const evidence = buildSpeechEvidence(
    { taskId: stimulus.taskId, expectedText: stimulus.promptText, kind: stimulus.kind, level: stimulus.level },
    {
      transcript: response.transcript ?? '',
      confidence: response.confidence ?? 0,
      latencyMs: response.latencyMs ?? 0,
      durationMs: response.durationMs ?? 0,
      speechDetected: response.speechDetected ?? false,
      provider: response.provider ?? 'webkit-speech-v1',
      retriedNoSpeech: response.retriedNoSpeech ?? 0,
      errorType: response.errorType,
    } as SpeechRecognitionResult,
    grade,
  );

  const features = numericFeatures(evidence);
  const metadata: Record<string, unknown> = {
    modality: 'speech',
    evidence: { ...evidence, transcript: evidence.transcript },
    features,
    event_payload: responseSubmittedPayload(evidence),
    features_event_payload: speechFeaturesEventPayload(evidence),
  };

  return {
    correct: grade.correct,
    score: grade.correct ? 1 : 0,
    actualResponse: grade.transcript,
    metadata,
  };
}

export function nextSpeechLevel(history: SpeechTrial[]): number {
  if (!history.length) return 1;
  return Math.min(3, history[history.length - 1]!.difficulty + 1);
}

const DOMAIN_BY_GAME: Record<string, AssessmentDomain> = {
  'sound-quest-adventure': 'phonological-awareness',
  'letter-bubble-pop': 'reading-fluency',
  'maze-runner-rush': 'attention-visual-search',
};

function buildDefinition(game: SpeechGameContent, description: string, ageRange: [number, number]): GameDefinition<SpeechTrial> {
  const levels = LEVEL_COUNTS[game.id] ?? game.levels.map(level => level.minTrials);
  return {
    id: game.id,
    name: game.title,
    description,
    domain: DOMAIN_BY_GAME[game.id],
    gameVersion: '3.0.0',
    ageRange,
    estimatedDurationMinutes: 5,
    difficultyLevels: [1, 2, 3],
    instructions: game.levels.map(level => `${level.subtitle}.`),
    totalTrials: levels.reduce((sum, count) => sum + count, 0),
    createTrial: createTrialFactory(game),
    evaluateResponse: (trial: Trial, response: unknown) => evaluateSpeechTrial(trial as SpeechTrial, response as SpeechResponseRecord),
    getNextDifficulty: (history: unknown[]) => nextSpeechLevel(history as SpeechTrial[]),
  };
}

export const soundQuestAdventure = buildDefinition(SOUND_QUEST_ADVENTURE, 'Read each word or sentence aloud to move the story forward.', [4, 10]);
export const letterBubblePop = buildDefinition(LETTER_BUBBLE_POP, 'Say the letters you see to pop the bubbles.', [4, 10]);
export const mazeRunnerRush = buildDefinition(MAZE_RUNNER_RUSH, 'Name each word as it flashes on the path.', [4, 10]);

export const speechAssessmentPlan: Array<GameDefinition<SpeechTrial>> = [soundQuestAdventure, letterBubblePop, mazeRunnerRush];