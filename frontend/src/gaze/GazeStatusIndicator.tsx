import type { EyeTrackingPhase } from './types';

const PHASE_LABELS: Record<EyeTrackingPhase, { label: string; tone: 'off' | 'ready' | 'busy' | 'error' }> = {
  UNAVAILABLE: { label: 'Eye tracking unavailable', tone: 'off' },
  NOT_CONFIGURED: { label: 'Eye tracking off', tone: 'off' },
  REQUESTED: { label: 'Getting the eye tracker ready…', tone: 'busy' },
  CALIBRATING: { label: 'Calibrating — look at the dots', tone: 'busy' },
  READY: { label: 'Eye tracking ready', tone: 'ready' },
  TRACKING: { label: 'Tracking where your eyes look', tone: 'ready' },
  DEGRADED: { label: 'Eye tracking works, but with lower confidence', tone: 'ready' },
  STOPPED: { label: 'Eye tracking off', tone: 'off' },
  ERROR: { label: 'Eye tracking unavailable', tone: 'error' },
};

export interface GazeStatusIndicatorProps {
  phase: EyeTrackingPhase;
  message?: string;
  visible: boolean;
}

export function GazeStatusIndicator({ phase, message, visible }: GazeStatusIndicatorProps) {
  if (!visible) return null;
  const tone = PHASE_LABELS[phase] ?? { label: 'Eye tracking off', tone: 'off' as const };
  return (
    <div className={`gaze-status gaze-status-${tone.tone}`} role="status" aria-live="polite">
      <span className="gaze-status-dot" />
      <span>{tone.label}</span>
      {message ? <small>{message}</small> : null}
    </div>
  );
}