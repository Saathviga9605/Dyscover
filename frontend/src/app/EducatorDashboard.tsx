import { useCallback, useEffect, useState } from 'react';
import {
  Badge,
  Card,
  ConfirmButton,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from '../components/ui';
import { useLanguage } from '../l10n';
import { api, type EducatorLearnerSummary } from '../services/apiClient';
import { useDomainLabel } from './domainLabels';

export function EducatorDashboard() {
  const { t } = useLanguage();
  const domainLabel = useDomainLabel();
  const [learners, setLearners] = useState<EducatorLearnerSummary[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  const load = useCallback(() => {
    setStatus('loading');
    api
      .getEducatorLearners()
      .then(list => {
        setLearners(list);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="parent-space">
      <PageHeader eyebrow={t('educator.eyebrow')} title={t('educator.title')}>
        <p className="page-lede">{t('educator.lede')}</p>
      </PageHeader>

      <div className="dashboard">
        <Card className="wide parent-welcome">
          <div>
            <Badge>{t('educator.authorizedBadge')}</Badge>
            <h2>{status === 'ready' ? learners.length : '—'}</h2>
            <p>{t('educator.howAccessWorks')}</p>
          </div>
          <div className="dashboard-map" aria-hidden="true">
            <span>✦</span>
            <span>✦</span>
            <span>✦</span>
            <span>✦</span>
            <i />
          </div>
        </Card>

        {status === 'loading' ? (
          <Card className="wide">
            <LoadingState label={t('educator.loading')} />
          </Card>
        ) : status === 'error' ? (
          <Card className="wide">
            <ErrorState message={t('educator.loadError')} onRetry={load} />
          </Card>
        ) : learners.length === 0 ? (
          <Card className="wide">
            <EmptyState>
              <strong>{t('educator.emptyTitle')}</strong>
              <br />
              {t('educator.emptyCopy')}
            </EmptyState>
          </Card>
        ) : (
          learners.map(learner => (
            <Card key={learner.child_id} className="wide">
              <div className="card-title-row">
                <h3>{learner.display_name}</h3>
                <Badge>
                  {t('educator.completedCount', { count: learner.completed_assessment_count })}
                </Badge>
              </div>
              <p className="notice">{t('educator.observationNotice')}</p>
              <dl className="domain-list">
                {learner.language_context.length ? (
                  <div>
                    <dt>{t('educator.languageContext')}</dt>
                    <dd>{learner.language_context.join(', ')}</dd>
                  </div>
                ) : null}
                {learner.domains.length ? (
                  learner.domains.map(domain => (
                    <div key={`${learner.child_id}-${domain.domain}`}>
                      <dt>{domainLabel(domain.domain)}</dt>
                      <dd>
                        {domain.accuracy !== null && domain.accuracy !== undefined
                          ? t('educator.accuracy', {
                              percent: domain.accuracy,
                              trials: domain.evidence_trials,
                            })
                          : t('educator.insufficient', { trials: domain.evidence_trials })}
                      </dd>
                    </div>
                  ))
                ) : (
                  <div>
                    <dt>{t('educator.observations')}</dt>
                    <dd>{t('educator.noEvidence')}</dd>
                  </div>
                )}
              </dl>
              <p className="subtle-text">
                {t('educator.practiceSummary', {
                  sessions: learner.practice_summary.completed_sessions,
                  activities: learner.practice_summary.activity_count,
                })}
              </p>
              <div className="card-actions">
                <ConfirmButton
                  label={t('educator.leave')}
                  confirmLabel={t('educator.leaveConfirm')}
                  prompt={t('educator.leavePrompt', { name: learner.display_name })}
                  onConfirm={async () => {
                    await api.leaveEducatorLearner(learner.child_id);
                    setLearners(current =>
                      current.filter(item => item.child_id !== learner.child_id)
                    );
                  }}
                />
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
