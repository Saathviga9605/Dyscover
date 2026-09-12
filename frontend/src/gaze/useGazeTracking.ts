import { useCallback, useEffect, useRef, useState } from 'react';
import { captureRegions } from './aoi';
import { GazeCollector } from './collector';
import { browserSupportsEyeTrackingCapability, NoopEyeTrackingProvider } from './provider';
import type { AoiRegion, EyeTrackingPhase, EyeTrackingProvider, GazeTrialData } from './types';
import { createEyeTrackingProvider } from './webgazerProvider';

const CONSENT_KEY = 'dyscover-gaze-consent';

export interface GazeStats {
  samples: number;
  aoiSamples: number;
}

export interface GazeTrackingController {
  capable: boolean;
  consented: boolean;
  phase: EyeTrackingPhase;
  message?: string;
  calibrating: boolean;
  tracking: boolean;
  previewStream: MediaStream | null;
  stats: GazeStats;
  calibrationCompleted: boolean;
  enable(): Promise<void>;
  disable(): void;
  finalizeCalibration(): void;
  setCalibrationPoint(x: number, y: number): Promise<void>;
  beginTrial(trialRef: string): Promise<void>;
  harvestTrial(trialRef: string): GazeTrialData | null;
  cleanup(): void;
}

const STATS_THROTTLE_MS = 250;

export function useGazeTracking(gameId: string): GazeTrackingController {
  const [capable] = useState(() => typeof window !== 'undefined' && browserSupportsEyeTrackingCapability());
  const [consented, setConsented] = useState(() => (typeof window !== 'undefined' ? window.localStorage.getItem(CONSENT_KEY) === 'true' : false));
  const [phase, setPhase] = useState<EyeTrackingPhase>('NOT_CONFIGURED');
  const [message, setMessage] = useState<string>();
  const [previewStream, setPreviewStream] = useState<MediaStream | null>(null);
  const [stats, setStats] = useState<GazeStats>({ samples: 0, aoiSamples: 0 });
  const [calibrationCompleted, setCalibrationCompleted] = useState(false);
  const providerRef = useRef<EyeTrackingProvider | null>(null);
  const collectorRef = useRef<GazeCollector | null>(null);
  const previewRef = useRef<MediaStream | null>(null);
  const lastStatsAt = useRef(0);

  const stopPreview = useCallback(() => {
    const stream = previewRef.current;
    previewRef.current = null;
    setPreviewStream(null);
    if (stream) for (const track of stream.getTracks()) track.stop();
  }, []);

  const startPreview = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
      previewRef.current = stream;
      setPreviewStream(stream);
    } catch {
      // The preview is cosmetic; tracking works without it.
    }
  }, []);

  useEffect(() => {
    if (!capable) {
      setPhase('UNAVAILABLE');
      providerRef.current = new NoopEyeTrackingProvider();
    }
  }, [capable]);

  useEffect(() => {
    return () => {
      void providerRef.current?.cleanup();
      providerRef.current = null;
      collectorRef.current = null;
      stopPreview();
    };
  }, [stopPreview]);

  const updateStats = useCallback((samples: number, aoiSamples: number) => {
    const now = performance.now();
    if (now - lastStatsAt.current < STATS_THROTTLE_MS) return;
    lastStatsAt.current = now;
    setStats({ samples, aoiSamples });
  }, []);

  const enable = useCallback(async () => {
    if (!capable) return;
    const provider = createEyeTrackingProvider();
    providerRef.current = provider;
    provider.setPhaseListener((next, text) => {
      setPhase(next);
      setMessage(text);
    });
    window.localStorage.setItem(CONSENT_KEY, 'true');
    setConsented(true);
    setCalibrationCompleted(false);
    const granted = await provider.requestAccess();
    if (!granted) {
      window.localStorage.setItem(CONSENT_KEY, 'false');
      setConsented(false);
      stopPreview();
      return;
    }
    void startPreview();
    await provider.beginCalibration();
    collectorRef.current = new GazeCollector({
      provider,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      onSampleStats: updateStats,
    });
  }, [capable, startPreview, stopPreview, updateStats]);

  const disable = useCallback(() => {
    void providerRef.current?.stopTracking();
    void providerRef.current?.cleanup();
    providerRef.current = null;
    collectorRef.current = null;
    stopPreview();
    window.localStorage.setItem(CONSENT_KEY, 'false');
    setConsented(false);
    setCalibrationCompleted(false);
    setPhase('STOPPED');
    setMessage(undefined);
  }, [stopPreview]);

  const finalizeCalibration = useCallback(() => {
    providerRef.current?.finishCalibration();
    setCalibrationCompleted(true);
  }, []);

  const setCalibrationPoint = useCallback(async (x: number, y: number) => {
    await providerRef.current?.setCalibrationPoint(x, y);
  }, []);

  const beginTrial = useCallback(
    async (trialRef: string) => {
      const collector = collectorRef.current;
      const provider = providerRef.current;
      if (!collector || !provider) return;
      const regions: AoiRegion[] = captureRegions(gameId);
      collector.setRegions(regions);
      setStats({ samples: 0, aoiSamples: 0 });
      try {
        await collector.start();
      } catch {
        // Tracking could not start; the trial proceeds without gaze.
      }
    },
    [gameId],
  );

  const harvestTrial = useCallback((trialRef: string): GazeTrialData | null => {
    const collector = collectorRef.current;
    if (!collector) return null;
    void collector.stop();
    const data = collector.completeTrial(trialRef);
    setStats({ samples: data.samples.length, aoiSamples: collector.aoiSampleCount() });
    if (!data.samples.length) return null;
    return data;
  }, []);

  const cleanup = useCallback(() => {
    void providerRef.current?.stopTracking();
    void providerRef.current?.cleanup();
    providerRef.current = null;
    collectorRef.current = null;
    stopPreview();
  }, [stopPreview]);

  return {
    capable,
    consented,
    phase,
    message,
    calibrating: phase === 'CALIBRATING' || phase === 'REQUESTED',
    tracking: phase === 'TRACKING',
    previewStream,
    stats,
    calibrationCompleted,
    enable,
    disable,
    finalizeCalibration,
    setCalibrationPoint,
    beginTrial,
    harvestTrial,
    cleanup,
  };
}