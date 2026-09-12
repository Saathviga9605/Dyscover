import { browserSupportsEyeTrackingCapability } from './provider';
import type { EyeTrackingPhase, EyeTrackingProvider } from './types';

const WEBAZER_CDN = 'https://webgazer.cs.brown.edu/webgazer.js';
const FACE_MESH_SOLUTION_PATH = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh';
const FACE_MESH_MODEL_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/face_mesh_landmarks.task';

type WebGazerHandle = {
  begin: (callback?: () => void) => Promise<void>;
  end: () => void;
  pause: () => void;
  resume: () => void;
  setGazeListener: (listener: (data: { x: number; y: number; t?: number } | null) => void) => WebGazerHandle;
  showVideo: (show: boolean) => WebGazerHandle;
  showPredictionPoints: (show: boolean) => WebGazerHandle;
  showFaceOverlay: (show: boolean) => WebGazerHandle;
  showFaceFeedbackBox: (show: boolean) => WebGazerHandle;
  addMouseEventListeners: () => WebGazerHandle;
  removeMouseEventListeners: () => WebGazerHandle;
  recordScreenPosition: (x: number, y: number, eventType: string) => WebGazerHandle;
  setTracker: (tracker: string) => WebGazerHandle;
  setRegression: (regression: string) => WebGazerHandle;
  params: { faceMeshSolutionPath?: string; faceMeshModelUrl?: string };
};

declare global {
  interface Window {
    webgazer?: WebGazerHandle;
  }
}

function loadWebGazerScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && window.webgazer) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = WEBAZER_CDN;
    script.async = true;
    script.onload = () => (window.webgazer ? resolve() : reject(new Error('WebGazer loaded but unavailable.')));
    script.onerror = () => reject(new Error('WebGazer could not be loaded.'));
    document.head.appendChild(script);
  });
}

export class WebGazerEyeTrackingProvider implements EyeTrackingProvider {
  readonly name = 'webgazer';
  readonly version = '1.0';
  phase: EyeTrackingPhase = 'NOT_CONFIGURED';
  private listener: ((phase: EyeTrackingPhase, message?: string) => void) | null = null;
  private onSample: ((x: number, y: number, confidence?: number) => void) | null = null;

  setPhaseListener(listener: (phase: EyeTrackingPhase, message?: string) => void): void {
    this.listener = listener;
  }

  private mark(phase: EyeTrackingPhase, message?: string): void {
    this.phase = phase;
    this.listener?.(phase, message);
  }

  async requestAccess(): Promise<boolean> {
    if (!browserSupportsEyeTrackingCapability()) {
      this.mark('UNAVAILABLE', 'Eye tracking requires a secure (HTTPS) connection with camera access.');
      return false;
    }
    this.mark('REQUESTED', 'Loading the eye-tracking engine…');
    try {
      await loadWebGazerScript();
      const webgazer = window.webgazer;
      if (!webgazer) throw new Error('WebGazer did not initialize.');
      webgazer.params.faceMeshSolutionPath = FACE_MESH_SOLUTION_PATH;
      webgazer.params.faceMeshModelUrl = FACE_MESH_MODEL_URL;
      webgazer.setRegression('ridge');
      webgazer.setTracker('TFFacemesh');
      webgazer.showVideo(false);
      webgazer.showPredictionPoints(false);
      webgazer.showFaceOverlay(false);
      webgazer.showFaceFeedbackBox(false);
      await webgazer.begin();
      this.mark('READY');
      return true;
    } catch (error) {
      this.mark('ERROR', error instanceof Error ? error.message : 'Eye tracking could not start.');
      return false;
    }
  }

  async beginCalibration(): Promise<void> {
    const webgazer = window.webgazer;
    if (!webgazer) {
      this.mark('ERROR', 'Eye tracking is not ready to calibrate.');
      return;
    }
    webgazer.addMouseEventListeners();
    this.mark('CALIBRATING', 'Look at each dot and click it.');
  }

  async setCalibrationPoint(x: number, y: number): Promise<void> {
    const webgazer = window.webgazer;
    if (!webgazer) return;
    webgazer.recordScreenPosition(x, y, 'click');
  }

  finishCalibration(): void {
    if (window.webgazer) window.webgazer.removeMouseEventListeners();
    this.mark('READY');
  }

  async startTracking(onSample: (x: number, y: number, confidence?: number) => void): Promise<void> {
    const webgazer = window.webgazer;
    if (!webgazer) {
      this.mark('ERROR', 'Eye tracking is not ready.');
      throw new Error('WebGazer is not ready.');
    }
    this.onSample = onSample;
    webgazer.setGazeListener((data) => {
      if (data && Number.isFinite(data.x) && Number.isFinite(data.y)) {
        onSample(data.x, data.y);
      }
    });
    webgazer.resume();
    this.mark('TRACKING');
  }

  async stopTracking(): Promise<void> {
    if (window.webgazer) window.webgazer.pause();
    this.onSample = null;
    this.mark('STOPPED');
  }

  async cleanup(): Promise<void> {
    this.onSample = null;
    if (window.webgazer) {
      try {
        webgazerCleanupEnd();
      } catch {
        // Provider may already be torn down.
      }
    }
    this.listener = null;
  }
}

function webgazerCleanupEnd(): void {
  window.webgazer?.removeMouseEventListeners();
  window.webgazer?.end();
  delete window.webgazer;
}

export function createEyeTrackingProvider(): EyeTrackingProvider {
  return new WebGazerEyeTrackingProvider();
}