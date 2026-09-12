export const GAZE_SCHEMA_VERSION = '1.0';

export type GazeQuality = 'tracking' | 'degraded' | 'out_of_order' | 'unavailable';

export type EyeTrackingPhase =
  | 'UNAVAILABLE'
  | 'NOT_CONFIGURED'
  | 'REQUESTED'
  | 'CALIBRATING'
  | 'READY'
  | 'TRACKING'
  | 'DEGRADED'
  | 'STOPPED'
  | 'ERROR';

export interface GazeSample {
  schemaVersion: string;
  timestampMs: number;
  x: number;
  y: number;
  confidence?: number;
  quality: GazeQuality;
  viewportWidth: number;
  viewportHeight: number;
  provider: string;
}

export interface Fixation {
  startTime: number;
  endTime: number;
  durationMs: number;
  x: number;
  y: number;
  targetType?: string;
  targetId?: string;
}

export interface AoiRegion {
  label: string;
  type: 'target' | 'option' | 'distractor' | 'instruction' | 'neutral';
  left: number;
  top: number;
  width: number;
  height: number;
  available: boolean;
  elementId?: string;
}

export interface RegionRef {
  type: AoiRegion['type'];
  label: string;
  elementId?: string;
}

export interface EyeTrackingProvider {
  readonly name: string;
  readonly version: string;
  phase: EyeTrackingPhase;
  setPhaseListener(listener: (phase: EyeTrackingPhase, message?: string) => void): void;
  requestAccess(): Promise<boolean>;
  beginCalibration(): Promise<void>;
  setCalibrationPoint(x: number, y: number): Promise<void>;
  finishCalibration(): void;
  startTracking(onSample: (x: number, y: number, confidence?: number) => void): Promise<void>;
  stopTracking(): Promise<void>;
  cleanup(): Promise<void>;
}

export interface GazeTrialData {
  trialRef: string;
  samples: GazeSample[];
  fixations: Fixation[];
  quality: GazeQuality;
  features: Record<string, number | null>;
}

export interface GazeBatchPayload {
  provider: string;
  providerVersion: string;
  quality: GazeQuality;
  schemaVersion: string;
  samples: Array<{
    x: number;
    y: number;
    timestamp_ms: number;
    confidence?: number;
    quality: GazeQuality;
    viewport_width: number;
    viewport_height: number;
  }>;
  fixations: Array<{
    start_timestamp_ms: number;
    end_timestamp_ms: number;
    duration_ms: number;
    x: number;
    y: number;
    target_type?: string;
    target_id?: string;
  }>;
  calibration_completed?: boolean;
}