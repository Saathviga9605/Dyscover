export function stimulusSignature(stimulus: unknown, gameId: string): string {
  try {
    return `${gameId}:${JSON.stringify(stimulus)}`;
  } catch {
    return gameId;
  }
}

export class StimulusSpacing {
  private readonly recent: string[] = [];

  constructor(private readonly window = 4, private readonly maxRetries = 6) {}

  isRecent(stimulus: unknown, gameId: string): boolean {
    if (this.window <= 0) return false;
    return this.recent.includes(stimulusSignature(stimulus, gameId));
  }

  push(stimulus: unknown, gameId: string): void {
    if (this.window <= 0) return;
    this.recent.push(stimulusSignature(stimulus, gameId));
    if (this.recent.length > this.window) this.recent.shift();
  }

  retryLimit(): number {
    return this.window <= 0 ? 0 : this.maxRetries;
  }
}