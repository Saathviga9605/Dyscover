import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Card, EmptyState, Mascot, PageHeader } from '../components/ui';
import { PracticeCard } from '../games/practice/PracticeCard';
import { api, type PersonalizationProfile, type PersonalizationRecommendations, type ProgressResponse } from '../services/apiClient';
import { progressMessage, recommendationLabel } from '../services/childPersonalization';
import { comparisonRows, dedupeRecommendations, domainLabel, formatPercent } from './dashboardUI';
import { ModalitySummaryCard } from './ModalitySummaryCard';
import { useLanguage } from '../l10n';

export function ParentDashboard() {
	const { t, language } = useLanguage();
	const [profile, setProfile] = useState<Awaited<ReturnType<typeof api.getProfile>> | null>(null);
	const [loading, setLoading] = useState(true);
	const [personalization, setPersonalization] = useState<{ profile: PersonalizationProfile | null; recommendations: PersonalizationRecommendations | null; progress: ProgressResponse | null }>({ profile: null, recommendations: null, progress: null });

	useEffect(() => {
		const childId = localStorage.getItem('dyscover-stage2-child-id');
		if (!childId) {
			setLoading(false);
			return;
		}
		api
			.listAssessments(childId)
			.then(assessments => {
				const storedAssessmentId = localStorage.getItem('dyscover-stage2-assessment-id');
				const known = storedAssessmentId ? assessments.find(assessment => assessment.id === storedAssessmentId) : undefined;
				const latest = known ?? assessments.at(-1);
				return latest ? api.getProfile(latest.id) : null;
			})
			.then(value => setProfile(value))
			.catch(() => setProfile(null))
			.finally(() => setLoading(false));
	}, []);

	useEffect(() => {
		const childId = localStorage.getItem('dyscover-stage2-child-id');
		if (!childId) return;
		api
			.getPersonalizationProfile(childId)
			.then(profile =>
				api
					.getPersonalizationRecommendations(childId, language)
					.then(recommendations =>
						api.getPersonalizationProgress(childId).then(progress => setPersonalization({ profile, recommendations, progress })),
					)
					.catch(() => setPersonalization({ profile, recommendations: null, progress: null })),
			)
			.catch(() => setPersonalization({ profile: null, recommendations: null, progress: null }));
	}, [language]);

	const hasObservedData = Boolean(profile?.observations.length);
	const observedDomains = profile && Object.keys(profile.domains).length ? Object.entries(profile.domains).map(([domain, value]) => ({ label: domainLabel(domain), accuracy: value.accuracy })) : [];
	const recommendations = personalization.recommendations ? dedupeRecommendations(personalization.recommendations.recommendations) : [];
	const progressRows = comparisonRows(personalization.progress);
	const progressNote = progressMessage(personalization.progress);

	return (
		<div className="parent-space">
			<div className="parent-topline">
				<span className="eyebrow">{t('parent.space')}{profile ? t('parent.modeSuffix', { mode: profile.mode }) : t('parent.researchMode')}</span>
				<Link className="text-link" to="/">{t('parent.backLink')} <span>↗</span></Link>
			</div>
			<PageHeader eyebrow={t('parent.headerEyebrow')} title={t('parent.headerTitle')}>
				<p className="page-lede">{t('parent.headerLede')}</p>
			</PageHeader>
			<div className="dashboard">
				<Card className="wide parent-welcome">
					<div>
						<Badge>{profile ? t('parent.welcomeBadge') : t('parent.readyBadge')}</Badge>
						<h2>{profile ? t('parent.welcomeTitle') : t('parent.welcomeReadyTitle')}</h2>
						<p>{profile ? t('parent.welcomeCopy') : t('parent.welcomeReadyCopy')}</p>
						<Link className="button" to="/child/home">{profile ? t('parent.runAnother') : t('parent.startSession')} <span>→</span></Link>
					</div>
					<div className="dashboard-map"><span>✦</span><span>✦</span><span>✦</span><span>✦</span><i /></div>
				</Card>

				<Card>
					<div className="card-title-row"><h3>{t('parent.profileCard')}</h3><span className="soft-icon">◌</span></div>
					{loading ? (
						<EmptyState>{t('parent.loading')}</EmptyState>
					) : hasObservedData ? (
						<div className="observed-list">{profile?.observations.map(observation => <p key={observation}>{observation}</p>)}</div>
					) : (
						<EmptyState><strong>{t('parent.noProfileYet')}</strong><br />{t('parent.noProfileHint')}</EmptyState>
					)}
				</Card>

				<Card>
					<div className="card-title-row"><h3>{t('parent.observedTitle')}</h3><span className="soft-icon">✦</span></div>
					{observedDomains.length ? (
						<div className="domain-list">
							{observedDomains.map(({ label, accuracy }) => (
								<div key={label}><span>{label}</span><strong>{t('parent.accuracyFormat', { percent: formatPercent(accuracy) })}</strong></div>
							))}
						</div>
					) : (
						<div className="empty-profile"><span>--</span><p>{t('parent.noDomains')}</p></div>
					)}
				</Card>

				<Card className="wide">
					<div className="card-title-row"><h3>{t('parent.modelStatus')}</h3><Badge>{profile?.model.status ?? t('parent.modelUnavailable')}</Badge></div>
					<div className="notice">{t('parent.modelNotice')}</div>
				</Card>

				<Card className="wide recommendation-card">
					<Mascot mood="happy" size="small" />
					<div>
						<div className="card-title-row"><h3>{t('parent.suggestionsTitle')}</h3>{personalization.profile && <Badge>{t('parent.stage5Badge')}</Badge>}</div>
						{recommendations.length ? (
							<div className="observed-list">
								{recommendations.map(rec => <p key={rec.reason}><strong>{rec.kind === 'neutral' ? t('parent.startingPoint') : recommendationLabel(rec)}</strong><br />{rec.reason}</p>)}
							</div>
						) : (
							<p className="notice">{t('parent.suggestionsNone')}</p>
						)}
					</div>
				</Card>

				<Card className="wide recommendation-card">
					<Mascot mood="thinking" size="small" />
					<div>
						<div className="card-title-row"><h3>{t('parent.progressTitle')}</h3>{personalization.profile && <Badge>{t('parent.cumulativeBadge')}</Badge>}</div>
						{progressRows.length ? (
							<div className="domain-list">
								{progressRows.map(row => <div key={row.label}><span>{row.label}</span><span>{row.deltaText}</span></div>)}
							</div>
						) : (
							<p className="notice">{progressNote}</p>
						)}
					</div>
				</Card>

				<ModalitySummaryCard dataQuality={profile?.data_quality ?? null} />

				<PracticeCard />
			</div>
		</div>
	);
}