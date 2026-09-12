import { useEffect, useState } from 'react';
import { Badge, Card } from '../../components/ui';
import { api, type NextPracticeActivity, type PracticeProgress } from '../../services/apiClient';
import { useLanguage } from '../../l10n';

export function PracticeCard() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<{ recommendation: NextPracticeActivity | null; progress: PracticeProgress | null }>({ recommendation: null, progress: null });

  useEffect(() => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!childId) return;
    let active = true;
    api
      .getNextPracticeActivity(childId, language)
      .then(recommendation => api.getPracticeProgress(childId).then(progress => { if (active) setData({ recommendation, progress }); }))
      .catch(() => { if (active) setData({ recommendation: null, progress: null }); });
    return () => { active = false; };
  }, [language]);

  const { recommendation, progress } = data;
  const hasActivity = Boolean(recommendation?.activity);

  return (
    <Card className="wide recommendation-card">
      <div className="card-title-row"><h3>{t('practice.suggestedTitle')}</h3>{progress && <Badge>{t('practice.supportBadge')}</Badge>}</div>
      {hasActivity ? (
        <>
          <p className="practice-suggestion"><strong>{t('practice.suggestedLine', { name: recommendation!.activity!.display_name })}</strong><br />{recommendation!.reason}</p>
          <div className="practice-progress-row"><span>{t('practice.completeSessions', { count: progress?.totals.sessions_completed ?? 0, word: progress?.totals.sessions_completed === 1 ? t('practice.sessionWord') : t('practice.sessionsWord') })}</span><span>{t('practice.activitiesCount', { count: progress?.totals.activities_completed ?? 0, word: progress?.totals.activities_completed === 1 ? t('practice.activityWord') : t('practice.activitiesWord') })}</span></div>
          {progress && progress.by_activity.length > 0 && <div className="domain-list">{(progress.by_activity.filter(item => item.completed > 0)).map(item => <div key={item.activity_id}><span>{item.activity_name}</span><span>{item.accuracy_observed !== undefined && item.accuracy_observed !== null ? t('practice.accuracyInPractice', { percent: Math.round(item.accuracy_observed * 100) }) : t('practice.completedCount', { count: item.completed })}</span></div>)}</div>}
          <p className="notice subtle">{progress?.note}</p>
        </>
      ) : (
        <p className="notice">{t('practice.suggestionNone')}</p>
      )}
    </Card>
  );
}