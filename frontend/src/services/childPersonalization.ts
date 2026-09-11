import { api, type ProgressResponse, type Recommendation } from './apiClient';
import type { GameDefinition } from '../games/engine';

export function clampDifficulty(level: number, levels: readonly number[]): number | undefined {
  if (!Number.isFinite(level) || !levels.length) return undefined;
  const min = Math.min(...levels);
  const max = Math.max(...levels);
  return level >= min && level <= max ? level : undefined;
}

export async function fetchRecommendedDifficulty(childId: string | null | undefined, game: Pick<GameDefinition, 'id' | 'difficultyLevels'>): Promise<number | undefined> {
  if (!childId || !game || !game.id) return undefined;
  try {
    const decision = await api.getPersonalizationDifficulty(childId, game.id);
    return clampDifficulty(decision.level, game.difficultyLevels);
  } catch {
    return undefined;
  }
}

export function progressMessage(progress: ProgressResponse | null | undefined): string | null {
  const points = progress?.points ?? [];
  if (points.length < 2) return points.length === 1 ? 'Complete another screening to see activity progress over time.' : 'Complete a screening to see activity progress over time.';
  if (!progress?.comparison) return 'Not enough completed activity across screenings for a comparison yet.';
  return null;
}

export function recommendationLabel(rec: Recommendation): string {
  return rec.target_domain_label ?? 'Activity';
}

export function shouldApplyDifficulty(engine: { session: { status: string }; trials: unknown[] } | null | undefined): boolean {
  return Boolean(engine && engine.session.status === 'NOT_STARTED' && engine.trials.length === 0);
}