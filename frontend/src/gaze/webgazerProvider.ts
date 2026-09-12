import { browserSupportsEyeTrackingCapability } from './provider';
import type { EyeTrackingPhase, EyeTrackingProvider } from './types';

const WEBAZER_CDN = 'https://webgazer.cs.brown.edu/webgazer.js';
const FACE_MESH_SOLUTION_PATH = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619';
const WATCHDOG_INTERVAL_MS = 1000;
const NO_SAMPLE_TIMEOUT_MS = 3000;

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

let injectedWebGazerScript: HTMLScriptElement | null = null;

function loadWebGazerScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && window.webgazer) {
      resolve();
      return;
    }
    if (injectedWebGazerScript?.isConnected) {
      const existing = injectedWebGazerScript;
      const timeout = window.setTimeout(() => reject(new Error('WebGazer could not be loaded.')), 15000);
      existing.onload = () => {
        window.clearTimeout(timeout);
        window.webgazer ? resolve() : reject(new Error('WebGazer loaded but unavailable.'));
      };
      existing.onerror = () => {
        window.clearTimeout(timeout);
        reject(new Error('WebGazer could not be loaded.'));
      };
      return;
    }
    const script = document.createElement('script');
    script.src = WEBAZER_CDN;
    script.async = true;
    injectedWebGazerScript = script;
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
  private lastSampleAt = 0;
  private watchdogTimer: number | undefined = undefined;

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
    this.lastSampleAt = performance.now();
    webgazer.setGazeListener((data) => {
      if (data && Number.isFinite(data.x) && Number.isFinite(data.y)) {
        this.lastSampleAt = performance.now();
        if (this.phase === 'DEGRADED') this.mark('TRACKING');
        onSample(data.x, data.y);
      }
    });
    webgazer.resume();
    this.mark('TRACKING');
    this.watchdogTimer = window.setInterval(() => {
      if (performance.now() - this.lastSampleAt > NO_SAMPLE_TIMEOUT_MS) {
        this.mark('DEGRADED', 'No face detected — check lighting and camera position.');
      }
    }, WATCHDOG_INTERVAL_MS);
  }

  async stopTracking(): Promise<void> {
    window.clearInterval(this.watchdogTimer);
    this.watchdogTimer = undefined;
    if (window.webgazer) window.webgazer.pause();
    this.onSample = null;
    this.mark('STOPPED');
  }

  async cleanup(): Promise<void> {
    window.clearInterval(this.watchdogTimer);
    this.watchdogTimer = undefined;
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
  injectedWebGazerScript?.remove();
  injectedWebGazerScript = null;
}

export function createEyeTrackingProvider(): EyeTrackingProvider {
  return new WebGazerEyeTrackingProvider();
}