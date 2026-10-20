import { useEffect, useState } from 'react';
import { Badge, Card } from '../components/ui';
import { api, type ModalitySummaryResponse } from '../services/apiClient';
import { useLanguage } from '../l10n';

export interface ModalitySummaryCardProps {
  dataQuality?: Record<string, unknown> | null;
  /** Assessment whose gaze/speech coverage is described. */
  assessmentId?: string | null;
}

/**
 * Describes which observation modalities were recorded. Missing modalities are
 * shown as "not recorded" — never as a zero measurement.
 */
export function ModalitySummaryCard({ dataQuality, assessmentId }: ModalitySummaryCardProps) {
  const { t } = useLanguage();
  const [summary, setSummary] = useState<ModalitySummaryResponse | null>(null);

  useEffect(() => {
    if (!assessmentId) {
      setSummary(null);
      return;
    }
    let active = true;
    api
      .getModalitySummary(assessmentId)
      .then(value => {
        if (active) setSummary(value);
      })
      .catch(() => {
        if (active) setSummary(null);
      });
    return () => {
      active = false;
    };
  }, [assessmentId]);

  const gazeAvailability =
    typeof dataQuality?.gaze_availability === 'number' ? dataQuality.gaze_availability : null;
  const speechAvailability =
    typeof dataQuality?.speech_availability === 'number' ? dataQuality.speech_availability : null;
  const gaze = summary?.gaze;
  const speech = summary?.speech;

  const trialWord = (count: number) => (count === 1 ? t('modal.trial') : t('modal.trials'));
  const gazeLine =
    gazeAvailability !== null
      ? t('modal.gazeTrialsPercent', { percent: Math.round(gazeAvailability * 100) })
      : gaze?.recorded
        ? t('modal.gazeRecordedLine', {
            samples: gaze.sample_count,
            trials: gaze.trial_count,
            trialWord: trialWord(gaze.trial_count),
            calibration: gaze.calibration_completed ? '' : t('modal.notCalibrated'),
          })
        : t('modal.gazeNotRecorded');
  const speechLine =
    speechAvailability !== null
      ? t('modal.speechTrialsPercent', { percent: Math.round(speechAvailability * 100) })
      : speech?.recorded
        ? t('modal.speechRecordedLine', {
            trials: speech.trial_count,
            trialWord: trialWord(speech.trial_count),
            captured: speech.transcript_available,
          })
        : t('modal.speechNotRecorded');

  return (
    <Card className="wide">
      <div className="card-title-row">
        <h3>{t('modal.howPlayed')}</h3>
        <Badge>{t('modal.observationBadge')}</Badge>
      </div>
      <dl className="domain-list">
        <div>
          <dt>{t('modal.eyeTracking')}</dt>
          <dd>{gazeLine}</dd>
        </div>
        <div>
          <dt>{t('modal.readingAloud')}</dt>
          <dd>{speechLine}</dd>
        </div>
      </dl>
      <p className="notice">{t('modal.privacyNote')}</p>
    </Card>
  );
}
