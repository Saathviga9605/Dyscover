import { useEffect, useState } from 'react';
import { Badge, Card } from '../../components/ui';
import { api, type NextPracticeActivity, type PracticeProgress } from '../../services/apiClient';

export function PracticeCard() {
  const [data, setData] = useState<{ recommendation: NextPracticeActivity | null; progress: PracticeProgress | null }>({ recommendation: null, progress: null });

  useEffect(() => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!childId) return;
    let active = true;
    api
      .getNextPracticeActivity(childId)
      .then(recommendation => api.getPracticeProgress(childId).then(progress => { if (active) setData({ recommendation, progress }); }))
      .catch(() => { if (active) setData({ recommendation: null, progress: null }); });
    return () => { active = false; };
  }, []);

  const { recommendation, progress } = data;
  const hasActivity = Boolean(recommendation?.activity);

  return (
    <Card className="wide recommendation-card">
      <div className="card-title-row"><h3>Suggested practice</h3>{progress && <Badge>Educational support</Badge>}</div>
      {hasActivity ? (
        <>
          <p className="practice-suggestion"><strong>Suggested practice: {recommendation!.activity!.display_name}</strong><br />{recommendation!.reason}</p>
          <div className="practice-progress-row"><span>{progress?.totals.sessions_completed ?? 0} complete practice session{progress?.totals.sessions_completed === 1 ? '' : 's'}</span><span>{progress?.totals.activities_completed ?? 0} practice {progress?.totals.activities_completed === 1 ? 'activity' : 'activities'}</span></div>
          {progress && progress.by_activity.length > 0 && <div className="domain-list">{(progress.by_activity.filter(item => item.completed > 0)).map(item => <div key={item.activity_id}><span>{item.activity_name}</span><span>{item.accuracy_observed !== undefined && item.accuracy_observed !== null ? `${Math.round(item.accuracy_observed * 100)}% accurate in practice` : `${item.completed} completed`}</span></div>)}</div>}
          <p className="notice subtle">{progress?.note}</p>
        </>
      ) : (
        <p className="notice">Suggested practice will appear here once there is enough activity to choose from.</p>
      )}
    </Card>
  );
}