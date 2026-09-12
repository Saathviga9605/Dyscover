import type { EyeTrackingPhase, EyeTrackingProvider } from './types';

export function browserSupportsEyeTrackingCapability(): boolean {
  if (typeof window === 'undefined') return false;
  if (!window.isSecureContext) return false;
  if (typeof navigator === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return false;
  return true;
}

export class NoopEyeTrackingProvider implements EyeTrackingProvider {
  readonly name = 'none';
  readonly version = '1.0';
  phase: EyeTrackingPhase = 'UNAVAILABLE';
  private listener: ((phase: EyeTrackingPhase, message?: string) => void) | null = null;

  setPhaseListener(listener: (phase: EyeTrackingPhase, message?: string) => void): void {
    this.listener = listener;
  }

  private mark(phase: EyeTrackingPhase, message?: string): void {
    this.phase = phase;
    this.listener?.(phase, message);
  }

  async requestAccess(): Promise<boolean> {
    this.mark('UNAVAILABLE', 'Eye tracking is not available on this device or browser.');
    return false;
  }

  async beginCalibration(): Promise<void> {
    this.mark('UNAVAILABLE', 'Eye tracking is not available.');
  }

  async setCalibrationPoint(_x: number, _y: number): Promise<void> {
    // No-op: no provider to calibrate.
  }

  finishCalibration(): void {
    this.mark('UNAVAILABLE');
  }

  async startTracking(_onSample: (x: number, y: number, confidence?: number) => void): Promise<void> {
    throw new Error('No eye-tracking provider is available.');
  }

  async stopTracking(): Promise<void> {
    this.mark('STOPPED');
  }

  async cleanup(): Promise<void> {
    this.listener = null;
  }
}

export function createFallbackProvider(): EyeTrackingProvider {
  return new NoopEyeTrackingProvider();
}