import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../components/ui';

const CALIBRATION_POINTS = [
  { left: 15, top: 15 },
  { left: 50, top: 15 },
  { left: 85, top: 15 },
  { left: 15, top: 50 },
  { left: 50, top: 50 },
  { left: 85, top: 50 },
  { left: 15, top: 85 },
  { left: 50, top: 85 },
  { left: 85, top: 85 },
];

export interface CalibrationOverlayProps {
  onFinished: () => void;
  onCancel: () => void;
  onCapturePoint: (x: number, y: number) => Promise<void>;
}

export function CalibrationOverlay({ onFinished, onCancel, onCapturePoint }: CalibrationOverlayProps) {
  const [index, setIndex] = useState(0);
  const overlayRef = useRef<HTMLDivElement>(null);

  const capture = useCallback(
    async (step: number) => {
      const overlay = overlayRef.current;
      if (!overlay) return;
      const rect = overlay.getBoundingClientRect();
      const point = CALIBRATION_POINTS[step];
      const x = rect.left + (rect.width * point.left) / 100;
      const y = rect.top + (rect.height * point.top) / 100;
      await onCapturePoint(x, y);
      if (step >= CALIBRATION_POINTS.length - 1) {
        onFinished();
      } else {
        setIndex(step + 1);
      }
    },
    [onCapturePoint, onFinished],
  );

  useEffect(() => {
    void capture(0);
  }, [capture]);

  const point = CALIBRATION_POINTS[index] ?? { left: 50, top: 50 };

  return (
    <div ref={overlayRef} className="calibration-overlay" aria-label="Eye tracking calibration">
      <p className="calibration-copy">Look at the dot, then click it. This teaches the eye tracker where you are looking.</p>
      <p className="calibration-progress">
        {index + 1} of {CALIBRATION_POINTS.length}
      </p>
      <button
        type="button"
        className="calibration-point"
        style={{ left: `${point.left}%`, top: `${point.top}%` }}
        onClick={() => void capture(index)}
        aria-label={`Calibration point ${index + 1}`}
      />
      <div className="calibration-cancel">
        <Button secondary onClick={onCancel}>
          Skip
        </Button>
      </div>
    </div>
  );
}