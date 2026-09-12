import { useEffect, useState } from 'react';
import { Badge, Card } from '../components/ui';
import { api } from '../services/apiClient';

const PARENT_SAFE_NOTE = 'Only numeric summaries are stored. The camera image and microphone audio are never saved or uploaded.';

export interface ModalitySummaryCardProps {
  dataQuality?: Record<string, unknown> | null;
}

interface GazeStatus {
  recording: boolean;
  total_samples: number;
  trialsWithSamples: number;
  schema_version: string;
}

export function ModalitySummaryCard({ dataQuality }: ModalitySummaryCardProps) {
  const [gazeStatus, setGazeStatus] = useState<GazeStatus | null>(null);

  useEffect(() => {
    let active = true;
    api
      .getGazeStatus()
      .then(status => {
        if (active) setGazeStatus(status);
      })
      .catch(() => {
        if (active) setGazeStatus(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const gazeAvailability = typeof dataQuality?.gaze_availability === 'number' ? dataQuality.gaze_availability : null;
  const speechAvailability = typeof dataQuality?.speech_availability === 'number' ? dataQuality.speech_availability : null;
  const zeroGaze = gazeAvailability === null && (gazeStatus?.total_samples ?? 0) === 0;

  return (
    <Card className="wide">
      <div className="card-title-row">
        <h3>How your child played</h3>
        <Badge>Observation modalities</Badge>
      </div>
      <div className="domain-list">
        {gazeAvailability !== null ? (
          <div><span>Eye tracking</span><strong>{Math.round(gazeAvailability * 100)}% of trials had gaze data</strong></div>
        ) : (
          <div><span>Eye tracking</span><strong>{zeroGaze ? 'Not recorded in the latest screening' : `${gazeStatus?.total_samples ?? 0} gaze samples recorded`}</strong></div>
        )}
        {speechAvailability !== null ? (
          <div><span>Reading aloud</span><strong>{Math.round(speechAvailability * 100)}% of trials had speech features</strong></div>
        ) : (
          <div><span>Reading aloud</span><strong>Read-aloud practice is optional</strong></div>
        )}
      </div>
      <p className="notice">{PARENT_SAFE_NOTE}</p>
    </Card>
  );
}