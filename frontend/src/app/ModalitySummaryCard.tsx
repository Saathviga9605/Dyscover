import { useEffect, useState } from 'react';
import { Badge, Card } from '../components/ui';
import { api, type ModalitySummaryResponse } from '../services/apiClient';

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
  const [summary, setSummary] = useState<ModalitySummaryResponse | null>(null);

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
    const assessmentId = window.localStorage.getItem('dyscover-stage2-assessment-id');
    if (assessmentId) {
      api
        .getModalitySummary(assessmentId)
        .then(value => {
          if (active) setSummary(value);
        })
        .catch(() => {
          if (active) setSummary(null);
        });
    }
    return () => {
      active = false;
    };
  }, []);

  const gazeAvailability = typeof dataQuality?.gaze_availability === 'number' ? dataQuality.gaze_availability : null;
  const speechAvailability = typeof dataQuality?.speech_availability === 'number' ? dataQuality.speech_availability : null;
  const zeroGaze = gazeAvailability === null && (gazeStatus?.total_samples ?? 0) === 0;
  const gaze = summary?.gaze;
  const speech = summary?.speech;

  const gazeLine = gaze ? (gaze.recorded
    ? `Recorded · ${gaze.sample_count} samples over ${gaze.trial_count} trial${gaze.trial_count === 1 ? '' : 's'}${gaze.calibration_completed ? '' : ' · not calibrated'}`
    : 'Not recorded in the latest screening') : null;
  const speechLine = speech ? (speech.recorded
    ? `Recorded · ${speech.trial_count} listening trial${speech.trial_count === 1 ? '' : 's'}, ${speech.transcript_available} with a captured answer`
    : 'Not recorded in the latest screening') : null;

  return (
    <Card className="wide">
      <div className="card-title-row">
        <h3>How your child played</h3>
        <Badge>Observation modalities</Badge>
      </div>
      <div className="domain-list">
        {gazeAvailability !== null ? (
          <div><span>Eye tracking</span><strong>{Math.round(gazeAvailability * 100)}% of trials had gaze data</strong></div>
        ) : gazeLine ? (
          <div><span>Eye tracking</span><strong>{gazeLine}</strong></div>
        ) : (
          <div><span>Eye tracking</span><strong>{zeroGaze ? 'Not recorded in the latest screening' : `${gazeStatus?.total_samples ?? 0} gaze samples recorded`}</strong></div>
        )}
        {speechAvailability !== null ? (
          <div><span>Reading aloud</span><strong>{Math.round(speechAvailability * 100)}% of trials had speech features</strong></div>
        ) : speechLine ? (
          <div><span>Reading aloud</span><strong>{speechLine}</strong></div>
        ) : (
          <div><span>Reading aloud</span><strong>Not recorded in the latest screening</strong></div>
        )}
      </div>
      <p className="notice">{PARENT_SAFE_NOTE}</p>
    </Card>
  );
}