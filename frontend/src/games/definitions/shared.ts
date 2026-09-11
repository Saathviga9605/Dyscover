import type { AssessmentDomain } from '../../types/assessment';
import type { SeededRandom, Trial } from '../engine';

export function makeTrial(index: number, sessionId: string, gameId: string, domain: AssessmentDomain, difficulty: number, stimulus: unknown, expectedResponse: unknown, metadata: Record<string, unknown> = {}): Trial {
  return { trialId: `${gameId}_trial_${index + 1}_${sessionId.slice(-6)}`, sessionId, gameId, gameVersion: '1.0.0', trialIndex: index, domain, difficulty, startedAt: new Date().toISOString(), stimulus, expectedResponse, score: 0, attemptCount: 0, errorCount: 0, metadata };
}
export function shuffledOptions(random: SeededRandom, target: string, pool: string[], count: number): string[] { return random.shuffle([target, ...pool.filter(item => item !== target)]).slice(0, count); }
