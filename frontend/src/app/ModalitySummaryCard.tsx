import { useEffect, useState } from 'react';
import { Badge, Card } from '../components/ui';
import { api, type ModalitySummaryResponse } from '../services/apiClient';
import { useLanguage } from '../l10n';

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
  const { t } = useLanguage();
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

  const trialWord = (count: number) => (count === 1 ? t('modal.trial') : t('modal.trials'));
  const gazeLine = gaze ? (gaze.recorded
    ? t('modal.gazeRecordedLine', { samples: gaze.sample_count, trials: gaze.trial_count, trialWord: trialWord(gaze.trial_count), calibration: gaze.calibration_completed ? '' : t('modal.notCalibrated') })
    : t('modal.gazeNotRecorded')) : null;
  const speechLine = speech ? (speech.recorded
    ? t('modal.speechRecordedLine', { trials: speech.trial_count, trialWord: trialWord(speech.trial_count), captured: speech.transcript_available })
    : t('modal.gazeNotRecorded')) : null;

  return (
    <Card className="wide">
      <div className="card-title-row">
        <h3>{t('modal.howPlayed')}</h3>
        <Badge>{t('modal.observationBadge')}</Badge>
      </div>
      <div className="domain-list">
        {gazeAvailability !== null ? (
          <div><span>{t('modal.eyeTracking')}</span><strong>{t('modal.gazeTrialsPercent', { percent: Math.round(gazeAvailability * 100) })}</strong></div>
        ) : gazeLine ? (
          <div><span>{t('modal.eyeTracking')}</span><strong>{gazeLine}</strong></div>
        ) : (
          <div><span>{t('modal.eyeTracking')}</span><strong>{zeroGaze ? t('modal.gazeNotRecorded') : t('modal.gazeSamplesRecorded', { samples: gazeStatus?.total_samples ?? 0 })}</strong></div>
        )}
        {speechAvailability !== null ? (
          <div><span>{t('modal.readingAloud')}</span><strong>{t('modal.speechTrialsPercent', { percent: Math.round(speechAvailability * 100) })}</strong></div>
        ) : speechLine ? (
          <div><span>{t('modal.readingAloud')}</span><strong>{speechLine}</strong></div>
        ) : (
          <div><span>{t('modal.readingAloud')}</span><strong>{t('modal.gazeNotRecorded')}</strong></div>
        )}
      </div>
      <p className="notice">{t('modal.privacyNote')}</p>
    </Card>
  );
}