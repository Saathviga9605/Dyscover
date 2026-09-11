export interface GazeSample { timestamp: number; x: number; y: number; confidence?: number; }
export interface Fixation { startTime: number; endTime: number; durationMs: number; x: number; y: number; targetType?: string; targetId?: string; }
export interface GazeCollector { start(): Promise<void>; stop(): Promise<void>; subscribe(listener: (sample: GazeSample) => void): () => void; }
export interface FixationEngine { push(sample: GazeSample): Fixation | null; flush(): Fixation | null; }
export interface GazeProvider { name: string; createCollector(): GazeCollector; }
