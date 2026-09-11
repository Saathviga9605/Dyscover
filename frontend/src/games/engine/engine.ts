import { DifficultyManager } from './difficulty';
import { createId, createSeededRandom } from './random';
import type { AssessmentEvent, AssessmentSession, EventType, GameDefinition, GameResult, Trial, TrialEvaluation } from './types';

export class GameEngine<TTrial extends Trial = Trial> {
  readonly session: AssessmentSession;
  readonly events: AssessmentEvent[] = [];
  readonly trials: TTrial[] = [];
  private eventSequence = 0;
  private trialStartedAt = 0;
  private readonly random;
  private readonly difficultyManager = new DifficultyManager();

  constructor(readonly definition: GameDefinition<TTrial>, session?: AssessmentSession, seed?: number) {
    this.random = createSeededRandom(seed);
    this.eventSequence = session?.eventSequence ?? 0;
    this.session = session ?? { sessionId: createId('session'), assessmentVersion: 'stage-2.0', startedAt: new Date().toISOString(), status: 'NOT_STARTED', games: [], currentGameIndex: 0, totalTrials: 0 };
  }

  start(): void { this.session.status = 'IN_PROGRESS'; this.emit('SESSION_STARTED'); this.emit('GAME_STARTED', { gameVersion: this.definition.gameVersion }); }
  pause(): void { if (this.session.status === 'IN_PROGRESS') { this.session.status = 'PAUSED'; this.emit('SESSION_PAUSED'); } }
  resume(): void { if (this.session.status === 'PAUSED') { this.session.status = 'IN_PROGRESS'; this.emit('SESSION_RESUMED'); } }
  beginTrial(index = this.trials.length): TTrial { const difficulty = this.difficultyManager.next(this.trials); const trial = this.definition.createTrial({ index, difficulty, random: this.random, sessionId: this.session.sessionId }); this.trialStartedAt = performance.now(); trial.startedAt = new Date().toISOString(); trial.stimulusPresentedAt = trial.startedAt; this.trials.push(trial); this.emit('TRIAL_STARTED', { trialIndex: index, difficulty }, trial.trialId); this.emit('STIMULUS_SHOWN', { stimulus: trial.stimulus }, trial.trialId); return trial; }
  recordResponse(trial: TTrial, response: unknown, evaluation?: TrialEvaluation): TTrial { const result = evaluation ?? this.definition.evaluateResponse(trial, response); const reactionTimeMs = Math.round(performance.now() - this.trialStartedAt); trial.actualResponse = result.actualResponse; trial.correct = result.correct; trial.score = result.score; trial.reactionTimeMs = reactionTimeMs; trial.responseAt = new Date().toISOString(); trial.metadata = { ...trial.metadata, ...result.metadata }; trial.attemptCount += 1; if (!result.correct) trial.errorCount += 1; this.emit('RESPONSE_SUBMITTED', { response, correct: result.correct, reactionTimeMs }, trial.trialId); return trial; }
  timeout(trial: TTrial): TTrial { trial.correct = false; trial.score = 0; trial.completedAt = new Date().toISOString(); trial.errorCount += 1; this.emit('TRIAL_TIMEOUT', { trialIndex: trial.trialIndex }, trial.trialId); return trial; }
  completeTrial(trial: TTrial): void { trial.completedAt = new Date().toISOString(); this.emit('TRIAL_COMPLETED', { correct: trial.correct, score: trial.score, reactionTimeMs: trial.reactionTimeMs }, trial.trialId); this.session.totalTrials = this.trials.length; }
  completeGame(): GameResult { const result: GameResult = { gameId: this.definition.id, domain: this.definition.domain, gameVersion: this.definition.gameVersion, trialsCompleted: this.trials.filter(trial => trial.completedAt).length, totalTrials: this.definition.totalTrials, accuracy: this.trials.length ? this.trials.filter(trial => trial.correct).length / this.trials.length : 0, meanReactionTimeMs: this.meanReactionTime(), completionRate: this.trials.length / this.definition.totalTrials, errorRate: this.trials.length ? this.trials.reduce((sum, trial) => sum + trial.errorCount, 0) / this.trials.length : 0, difficultyProgression: this.trials.map(trial => trial.difficulty), hintsUsed: this.events.filter(event => event.eventType === 'HINT_USED').length }; this.session.games = [...this.session.games.filter(item => item.gameId !== result.gameId), result]; this.emit('GAME_COMPLETED', result as unknown as Record<string, unknown>); return result; }
  completeSession(): void { this.session.status = 'COMPLETED'; this.session.completedAt = new Date().toISOString(); this.emit('SESSION_COMPLETED', { games: this.session.games.length, totalTrials: this.session.totalTrials }); }
  emit(eventType: EventType, payload: Record<string, unknown> = {}, trialId?: string): AssessmentEvent { this.session.eventSequence = ++this.eventSequence; const event: AssessmentEvent = { eventId: createId('event'), sessionId: this.session.sessionId, trialId, gameId: this.definition.id, timestamp: new Date().toISOString(), performanceTime: performance.now(), eventType, sequenceNumber: this.eventSequence, payload, schemaVersion: '2.0' }; this.events.push(event); return event; }
  private meanReactionTime(): number { const measured = this.trials.map(trial => trial.reactionTimeMs).filter((value): value is number => typeof value === 'number'); return measured.length ? Math.round(measured.reduce((sum, value) => sum + value, 0) / measured.length) : 0; }
}
