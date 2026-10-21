import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorState, LoadingState, PageHeader } from '../components/ui';
import { useLanguage } from '../l10n';
import type { MessageKey } from '../l10n/messages/en';
import {
  api,
  ApiError,
  type ResearchFeature,
  type ResearchOverview,
  type ResearchPredictionResponse,
} from '../services/apiClient';
import { useChildren } from './ChildContext';

/**
 * Synthetic research predictor.
 *
 * Shows the real output of the synthetic-data research model for a child's real,
 * stored game observations. It lives on its own page (never on the parent
 * screening card), the server only serves it when research mode is enabled, and
 * every number is labelled as conditional on simulated training data.
 */
export function ResearchPredictor() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const isEducator = user?.role === 'educator';
  const { children: ownChildren } = useChildren();
  const [learners, setLearners] = useState<Array<{ id: string; name: string }>>([]);
  const childOptions = isEducator
    ? learners
    : ownChildren.map(child => ({ id: child.id, name: child.display_name }));
  const [childId, setChildId] = useState('');
  const [overview, setOverview] = useState<ResearchOverview | null>(null);
  const [overviewState, setOverviewState] = useState<
    'idle' | 'loading' | 'ready' | 'disabled' | 'error'
  >('idle');
  const [assessmentId, setAssessmentId] = useState('');
  const [prediction, setPrediction] = useState<ResearchPredictionResponse | null>(null);
  const [runState, setRunState] = useState<'idle' | 'running' | 'error'>('idle');

  useEffect(() => {
    if (!isEducator) return;
    api
      .getEducatorLearners()
      .then(rows => setLearners(rows.map(row => ({ id: row.child_id, name: row.display_name }))))
      .catch(() => setLearners([]));
  }, [isEducator]);

  useEffect(() => {
    if (!childId && childOptions.length > 0) setChildId(childOptions[0].id);
  }, [childId, childOptions]);

  const loadOverview = useCallback(() => {
    if (!childId) return;
    setOverviewState('loading');
    setPrediction(null);
    api
      .getResearchOverview(childId)
      .then(value => {
        setOverview(value);
        const firstCompleted = value.assessments.find(item => item.status === 'completed');
        setAssessmentId(firstCompleted?.assessment_id ?? '');
        setOverviewState('ready');
      })
      .catch(error =>
        setOverviewState(error instanceof ApiError && error.status === 404 ? 'disabled' : 'error')
      );
  }, [childId]);
  useEffect(loadOverview, [loadOverview]);

  const run = () => {
    if (!childId || !assessmentId) return;
    setRunState('running');
    api
      .runResearchPrediction(childId, assessmentId)
      .then(value => {
        setPrediction(value);
        setRunState('idle');
      })
      .catch(() => setRunState('error'));
  };

  const header = (
    <PageHeader eyebrow={t('researchPredictor.eyebrow')} title={t('researchPredictor.title')}>
      <p>{t('researchPredictor.intro')}</p>
    </PageHeader>
  );

  if (overviewState === 'disabled') {
    return (
      <main className="page research-page">
        {header}
        <Card className="research-card">
          <p role="status">
            <strong>{t('researchPredictor.disabledTitle')}</strong>
          </p>
          <p>{t('researchPredictor.disabledCopy')}</p>
        </Card>
      </main>
    );
  }

  return (
    <main className="page research-page">
      {header}
      <div className="research-warning" role="note">
        <strong>{t('researchPredictor.warningTitle')}</strong>
        <p>{t('researchPredictor.warningCopy')}</p>
      </div>

      <Card className="research-card">
        <h2>{t('researchPredictor.chooseTitle')}</h2>
        {childOptions.length === 0 ? (
          <p className="notice">{t('researchPredictor.noChildren')}</p>
        ) : (
          <div className="research-controls">
            <label>
              <span>{t('researchPredictor.childLabel')}</span>
              <select value={childId} onChange={event => setChildId(event.target.value)}>
                {childOptions.map(child => (
                  <option key={child.id} value={child.id}>
                    {child.name}
                  </option>
                ))}
              </select>
            </label>
            {overviewState === 'loading' && <LoadingState />}
            {overviewState === 'error' && <ErrorState onRetry={loadOverview} />}
            {overviewState === 'ready' && overview && (
              <>
                <label>
                  <span>{t('researchPredictor.assessmentLabel')}</span>
                  <select
                    value={assessmentId}
                    onChange={event => {
                      setAssessmentId(event.target.value);
                      setPrediction(null);
                    }}
                    disabled={overview.assessments.length === 0}
                  >
                    {overview.assessments.length === 0 && (
                      <option value="">{t('researchPredictor.noAssessments')}</option>
                    )}
                    {overview.assessments.map(item => (
                      <option
                        key={item.assessment_id}
                        value={item.assessment_id}
                        disabled={item.status !== 'completed'}
                      >
                        {formatAssessment(item, t)}
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  onClick={run}
                  disabled={!assessmentId || !overview.model || runState === 'running'}
                >
                  {runState === 'running'
                    ? t('researchPredictor.running')
                    : t('researchPredictor.run')}
                </Button>
              </>
            )}
          </div>
        )}
        {overviewState === 'ready' && overview && !overview.model && (
          <div className="screening-unavailable" role="status">
            <p>
              <strong>{t('researchPredictor.status.no_research_model.title')}</strong>
            </p>
            <p>{t('researchPredictor.status.no_research_model.copy')}</p>
          </div>
        )}
        {runState === 'error' && (
          <ErrorState message={t('researchPredictor.runError')} onRetry={run} />
        )}
      </Card>

      {prediction && <PredictionView prediction={prediction} />}
      {overviewState === 'ready' && overview?.model && <ModelCard overview={overview} />}
    </main>
  );
}

function formatAssessment(
  item: ResearchOverview['assessments'][number],
  t: (key: MessageKey, values?: Record<string, string | number>) => string
): string {
  const when = item.completed_at ?? item.created_at;
  const date = when ? new Date(when).toLocaleString() : '';
  const status = item.status === 'completed' ? '' : ` (${t('researchPredictor.notCompleted')})`;
  return `${date}${status}${item.has_prediction ? ' ✓' : ''}`;
}

function PredictionView({ prediction }: { prediction: ResearchPredictionResponse }) {
  const { t } = useLanguage();
  const { result, model } = prediction;
  if (prediction.status !== 'available' || !result || !model) {
    return (
      <Card className="research-card">
        <div className="screening-unavailable" role="status" aria-live="polite">
          <p>
            <strong>{t(`researchPredictor.status.${prediction.status}.title`)}</strong>
          </p>
          <p>{t(`researchPredictor.status.${prediction.status}.copy`)}</p>
          {prediction.reasons.length > 0 && (
            <ul className="plain-list">
              {prediction.reasons.map(reason => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    );
  }
  const calibrated = result.output_type === 'calibrated_probability';
  const shown = prediction.features.filter(item => item.available);
  const missing = prediction.features.filter(item => !item.available);
  return (
    <Card className="research-card research-result">
      <div className="card-title-row">
        <h2>{t('researchPredictor.resultTitle')}</h2>
        <Badge>{t('researchPredictor.badge')}</Badge>
      </div>
      <div role="status" aria-live="polite">
        <p className="research-score-line">
          <span className="research-score-label">
            {calibrated
              ? t('researchPredictor.scoreLabel')
              : t('researchPredictor.scoreLabelUncalibrated')}
          </span>{' '}
          <span className="screening-percent" data-testid="research-score">
            {result.score_percent}%
          </span>
        </p>
        <span className="screening-meter" aria-hidden="true">
          <span style={{ width: `${result.score_percent}%` }} />
        </span>
        <p className="screening-meaning">
          <strong>
            {calibrated
              ? t('researchPredictor.meaningCalibrated')
              : t('researchPredictor.meaningScore')}
          </strong>
        </p>
      </div>
      <p>{t('researchPredictor.neverConfirms')}</p>
      {prediction.notes.length > 0 && (
        <ul className="plain-list research-notes">
          {prediction.notes.map(note => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <p className="notice">
        {t('researchPredictor.basedOn', {
          scored: prediction.observations.scored_trials,
          unscored: prediction.observations.unscored_trials,
          version: model.model_version,
        })}
      </p>

      <h3>{t('researchPredictor.featuresTitle')}</h3>
      <p>{t('researchPredictor.featuresIntro')}</p>
      <div className="research-table-wrap">
        <table className="research-table">
          <thead>
            <tr>
              <th scope="col">{t('researchPredictor.colFeature')}</th>
              <th scope="col">{t('researchPredictor.colValue')}</th>
              <th scope="col">{t('researchPredictor.colTypical')}</th>
              <th scope="col">{t('researchPredictor.colEffect')}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(item => (
              <FeatureRow key={item.name} item={item} />
            ))}
          </tbody>
        </table>
      </div>
      {missing.length > 0 && (
        <p className="notice">
          {t('researchPredictor.missingFeatures', {
            names: missing.map(item => t(`researchPredictor.feature.${item.name}`)).join(', '),
          })}
        </p>
      )}
    </Card>
  );
}

function formatValue(name: string, value: number | null): string {
  if (value === null) return '—';
  if (name.endsWith('_accuracy') || name === 'completion_rate' || name.endsWith('_rate'))
    return `${Math.round(value * 100)}%`;
  if (name.endsWith('_ms')) return `${Math.round(value).toLocaleString()} ms`;
  if (name.endsWith('_ms2')) return `${Math.round(value).toLocaleString()} ms²`;
  return `${Math.round(value * 10) / 10}`;
}

function FeatureRow({ item }: { item: ResearchFeature }) {
  const { t } = useLanguage();
  // score_change_if_typical = score(with typical value) - score(actual); its negation is
  // how much this observed value moved the model's score, in percentage points.
  const points =
    item.score_change_if_typical === null ? null : Math.round(-item.score_change_if_typical * 100);
  return (
    <tr>
      <th scope="row">
        {t(`researchPredictor.feature.${item.name}`)}
        {item.outside_training_range && (
          <span className="research-flag"> {t('researchPredictor.outsideRange')}</span>
        )}
      </th>
      <td>{formatValue(item.name, item.value)}</td>
      <td>{formatValue(item.name, item.training_median)}</td>
      <td>
        {points === null || points === 0
          ? t('researchPredictor.effectNone')
          : points > 0
            ? t('researchPredictor.effectUp', { points })
            : t('researchPredictor.effectDown', { points: -points })}
      </td>
    </tr>
  );
}

function ModelCard({ overview }: { overview: ResearchOverview }) {
  const { t } = useLanguage();
  const model = overview.model!;
  const metric = (value: number | null) => (value === null ? '—' : value.toFixed(3));
  return (
    <Card className="research-card">
      <h2>{t('researchPredictor.modelTitle')}</h2>
      <dl className="domain-list">
        <div>
          <dt>{t('researchPredictor.modelName')}</dt>
          <dd>
            {model.model_name} · v{model.model_version}
          </dd>
        </div>
        <div>
          <dt>{t('researchPredictor.trainingData')}</dt>
          <dd>{t('researchPredictor.trainingDataValue')}</dd>
        </div>
        <div>
          <dt>{t('researchPredictor.target')}</dt>
          <dd>{model.target_definition}</dd>
        </div>
        <div>
          <dt>{t('researchPredictor.syntheticMetrics')}</dt>
          <dd>
            {t('researchPredictor.syntheticMetricsValue', {
              auc: metric(model.synthetic_test_metrics.roc_auc),
              participants: model.synthetic_test_counts?.participants ?? 0,
            })}
          </dd>
        </div>
        <div>
          <dt>{t('researchPredictor.checksum')}</dt>
          <dd>
            <code>{model.artifact_sha256.slice(0, 16)}…</code>
          </dd>
        </div>
      </dl>
      <p className="notice">{t('researchPredictor.metricsCaveat')}</p>
    </Card>
  );
}
