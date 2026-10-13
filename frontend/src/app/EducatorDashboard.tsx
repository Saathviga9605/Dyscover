import { useEffect, useState } from 'react';
import { Badge, Card, EmptyState, PageHeader } from '../components/ui';
import { api, type EducatorLearnerSummary } from '../services/apiClient';

export function EducatorDashboard() {
  const [learners, setLearners] = useState<EducatorLearnerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const educatorId = localStorage.getItem('dyscover-educator-id');
    if (!educatorId) {
      setError('Add an educator ID in localStorage as dyscover-educator-id to view this dashboard.');
      setLoading(false);
      return;
    }

    api
      .getEducatorLearners(educatorId)
      .then(setLearners)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'The educator dashboard could not be loaded.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="parent-space">
      <PageHeader eyebrow="Educator workspace" title="Learner overview">
        <p className="page-lede">Review authorized learner summaries, completed activity history, and educational support opportunities without exposing raw assessment traces.</p>
      </PageHeader>

      <div className="dashboard">
        <Card className="wide parent-welcome">
          <div>
            <Badge>Authorized learners</Badge>
            <h2>{learners.length}</h2>
            <p>Only learners with a valid educator authorization are listed here.</p>
          </div>
          <div className="dashboard-map"><span>✦</span><span>✦</span><span>✦</span><span>✦</span><i /></div>
        </Card>

        {loading ? (
          <Card className="wide"><EmptyState>Loading learner observations…</EmptyState></Card>
        ) : error ? (
          <Card className="wide"><EmptyState>{error}</EmptyState></Card>
        ) : learners.length === 0 ? (
          <Card className="wide"><EmptyState>No learners are currently authorized for this educator.</EmptyState></Card>
        ) : (
          learners.map(learner => (
            <Card key={learner.child_id} className="wide">
              <div className="card-title-row">
                <h3>{learner.display_name}</h3>
                <Badge>{learner.completed_assessment_count} completed</Badge>
              </div>

              <p className="notice">{learner.observation_summary}</p>

              <div className="domain-list">
                {learner.language_context.length ? (
                  <div key="language-context"><span>Language context</span><strong>{learner.language_context.join(', ')}</strong></div>
                ) : null}
                {learner.domains.length ? (
                  learner.domains.map(domain => (
                    <div key={`${learner.child_id}-${domain.domain}`}>
                      <span>{domain.domain}</span>
                      <strong>{domain.accuracy !== null && domain.accuracy !== undefined ? `${domain.accuracy}% accurate` : `${domain.evidence_trials} trials`}</strong>
                    </div>
                  ))
                ) : (
                  <div><span>Observations</span><strong>No direct domain evidence yet</strong></div>
                )}
              </div>

              <div className="observed-list">
                <p><strong>Practice:</strong> {learner.practice_summary.completed_sessions} completed sessions across {learner.practice_summary.activity_count} activities.</p>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
