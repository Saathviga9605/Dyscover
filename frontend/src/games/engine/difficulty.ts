import type { Trial } from './types';

export class DifficultyManager {
  constructor(private readonly minimum = 1, private readonly maximum = 5, private readonly initial?: number) {}
  next(history: Trial[]): number {
    const recent = history.slice(-3);
    if (recent.length < 3) return history.at(-1)?.difficulty ?? this.seed();
    const accuracy = recent.filter(trial => trial.correct).length / recent.length;
    const averageTime = recent.reduce((sum, trial) => sum + (trial.reactionTimeMs ?? 0), 0) / recent.length;
    if (accuracy >= .8 && averageTime > 0 && averageTime < 5000) return Math.min(this.maximum, recent.at(-1)!.difficulty + 1);
    if (accuracy <= .34 || recent.some(trial => trial.errorCount >= 3)) return Math.max(this.minimum, recent.at(-1)!.difficulty - 1);
    return recent.at(-1)!.difficulty;
  }
  private seed(): number {
    if (this.initial === undefined) return this.minimum;
    return Math.max(this.minimum, Math.min(this.maximum, Math.round(this.initial)));
  }
}
