import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Card, ErrorState, LoadingState } from '../components/ui';
import { useLanguage } from '../l10n';
import { api, type ScreeningResponse } from '../services/apiClient';
import { useDomainLabel } from './domainLabels';

/**
 * Dyslexia risk screening card.
 *
 * A percentage is shown only when the backend returns a result from an eligible,
 * validated model, and it is labelled by what the model actually outputs. Every
 * other state explains honestly what is and is not available.
 */
export function ScreeningCard({ childId }: { childId: string }) {
  const { t, locale } = useLanguage();
  const domainLabel = useDomainLabel();
  const [data, setData] = useState<ScreeningResponse | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  const load = useCallback(() => {
    setState('loading');
    api
      .getScreening(childId)
      .then(value => {
        setData(value);
        setState('ready');
      })
      .catch(() => setState('error'));
  }, [childId]);
  useEffect(load, [load]);

  const body = (() => {
    if (state === 'loading') return <LoadingState />;
    if (state === 'error' || !data) return <ErrorState onRetry={load} />;
    const { result, model, observations } = data;
    const assessed = data.assessment_completed_at
      ? new Date(data.assessment_completed_at).toLocaleDateString(locale)
      : null;
    const isProbability = result?.output_type === 'calibrated_probability';
    return (
      <>
        {result && model ? (
          <div className="screening-result">
            <div className="screening-score" aria-hidden="true">
              <span className="screening-percent">{result.score_percent}%</span>
              <span className="screening-meter">
                <span style={{ width: `${result.score_percent}%` }} />
              </span>
            </div>
            <p className="visually-hidden">
              {t('screening.scoreAria', { percent: result.score_percent })}
            </p>
            <p className="screening-meaning">
              <strong>
                {isProbability ? t('screening.meaningProbability') : t('screening.meaningResearch')}
              </strong>
            </p>
            {result.band && (
              <p className="screening-band">
                <span aria-hidden="true">
                  {result.band === 'higher' ? '▲' : result.band === 'lower' ? '▽' : '◆'}
                </span>{' '}
                {t(`screening.band.${result.band}`)}
              </p>
            )}
            <dl className="domain-list">
              <div>
                <dt>{t('screening.model')}</dt>
                <dd>
                  {model.model_name} · v{model.model_version}
                </dd>
              </div>
              {assessed && (
                <div>
                  <dt>{t('screening.assessmentDate')}</dt>
                  <dd>{assessed}</dd>
                </div>
              )}
            </dl>
          </div>
        ) : (
          <div className="screening-unavailable" role="status">
            <p>
              <strong>{t(`screening.status.${data.status}.title`)}</strong>
            </p>
            <p>{t(`screening.status.${data.status}.copy`)}</p>
          </div>
        )}

        {data.assessment_id && (
          <div className="screening-section">
            <h4>{t('screening.evidenceTitle')}</h4>
            <p>
              {t('screening.evidenceCounts', {
                scored: observations.scored_trials,
                unscored: observations.unscored_trials,
              })}
            </p>
            {observations.strengths.length > 0 && (
              <p>
                <strong>{t('screening.strengths')}</strong>{' '}
                {observations.strengths.map(domainLabel).join(', ')}
              </p>
            )}
            {observations.support_areas.length > 0 && (
              <p>
                <strong>{t('screening.supportAreas')}</strong>{' '}
                {observations.support_areas.map(domainLabel).join(', ')}
              </p>
            )}
          </div>
        )}

        <div className="screening-section">
          <h4>{t('screening.limitsTitle')}</h4>
          <ul className="plain-list">
            <li>{t('screening.limitNotDiagnosis')}</li>
            <li>{t('screening.limitLowHigh')}</li>
            <li>{t('screening.limitFactors')}</li>
          </ul>
        </div>
        <div className="screening-section">
          <h4>{t('screening.nextTitle')}</h4>
          <ul className="plain-list">
            <li>{t('screening.nextTalk')}</li>
            <li>{t('screening.nextAssessment')}</li>
            <li>{t('screening.nextPractice')}</li>
            <li>{t('screening.nextProgress')}</li>
          </ul>
        </div>
      </>
    );
  })();

  return (
    <Card className="wide screening-card">
      <div className="card-title-row">
        <h3>{t('screening.title')}</h3>
        <Badge>{t('screening.badge')}</Badge>
      </div>
      {body}
    </Card>
  );
}

/**
 * Link to the separate research page, rendered only when the server has research
 * mode enabled (the overview request 404s otherwise). It never shows a score here.
 */
export function ResearchLink({ childId }: { childId: string }) {
  const { t } = useLanguage();
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let active = true;
    api
      .getResearchOverview(childId)
      .then(() => active && setEnabled(true))
      .catch(() => active && setEnabled(false));
    return () => {
      active = false;
    };
  }, [childId]);
  if (!enabled) return null;
  return (
    <p className="wide research-link">
      <Link to="/research/predictor">{t('researchPredictor.dashboardLink')}</Link>
    </p>
  );
}
