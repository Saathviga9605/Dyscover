import { useCallback, useEffect, useRef, useState } from 'react';
import { captureRegions } from './aoi';
import { GazeCollector } from './collector';
import { browserSupportsEyeTrackingCapability, NoopEyeTrackingProvider } from './provider';
import type { AoiRegion, EyeTrackingPhase, EyeTrackingProvider, GazeTrialData } from './types';
import { createEyeTrackingProvider } from './webgazerProvider';

const CONSENT_KEY = 'dyscover-gaze-consent';

export interface GazeTrackingController {
  capable: boolean;
  consented: boolean;
  phase: EyeTrackingPhase;
  message?: string;
  calibrating: boolean;
  tracking: boolean;
  enable(): Promise<void>;
  disable(): void;
  finalizeCalibration(): void;
  setCalibrationPoint(x: number, y: number): Promise<void>;
  beginTrial(trialRef: string): Promise<void>;
  harvestTrial(trialRef: string): GazeTrialData | null;
  cleanup(): void;
}

export function useGazeTracking(gameId: string): GazeTrackingController {
  const [capable] = useState(() => typeof window !== 'undefined' && browserSupportsEyeTrackingCapability());
  const [consented, setConsented] = useState(() => (typeof window !== 'undefined' ? window.localStorage.getItem(CONSENT_KEY) === 'true' : false));
  const [phase, setPhase] = useState<EyeTrackingPhase>('NOT_CONFIGURED');
  const [message, setMessage] = useState<string>();
  const providerRef = useRef<EyeTrackingProvider | null>(null);
  const collectorRef = useRef<GazeCollector | null>(null);

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
    };
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
    const granted = await provider.requestAccess();
    if (!granted) {
      window.localStorage.setItem(CONSENT_KEY, 'false');
      setConsented(false);
      return;
    }
    await provider.beginCalibration();
    collectorRef.current = new GazeCollector({ provider, viewportWidth: window.innerWidth, viewportHeight: window.innerHeight });
  }, [capable]);

  const disable = useCallback(() => {
    void providerRef.current?.stopTracking();
    void providerRef.current?.cleanup();
    providerRef.current = null;
    collectorRef.current = null;
    window.localStorage.setItem(CONSENT_KEY, 'false');
    setConsented(false);
    setPhase('STOPPED');
    setMessage(undefined);
  }, []);

  const finalizeCalibration = useCallback(() => {
    providerRef.current?.finishCalibration();
  }, []);

  const setCalibrationPoint = useCallback(async (x: number, y: number) => {
    await providerRef.current?.setCalibrationPoint(x, y);
  }, []);

  const beginTrial = useCallback(
    async (trialRef: string) => {
      const collector = collectorRef.current;
      const provider = providerRef.current;
      if (!collector || !provider || provider.phase !== 'TRACKING' && provider.phase !== 'READY') return;
      const regions: AoiRegion[] = captureRegions(gameId);
      collector.setRegions(regions);
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
    if (!data.samples.length) return null;
    return data;
  }, []);

  const cleanup = useCallback(() => {
    void providerRef.current?.stopTracking();
    void providerRef.current?.cleanup();
    providerRef.current = null;
    collectorRef.current = null;
  }, []);

  return {
    capable,
    consented,
    phase,
    message,
    calibrating: phase === 'CALIBRATING' || phase === 'REQUESTED',
    tracking: phase === 'TRACKING',
    enable,
    disable,
    finalizeCalibration,
    setCalibrationPoint,
    beginTrial,
    harvestTrial,
    cleanup,
  };
}