import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Card, EmptyState, Mascot, PageHeader } from '../components/ui';
import { PracticeCard } from '../games/practice/PracticeCard';
import { api, type PersonalizationProfile, type PersonalizationRecommendations, type ProgressResponse } from '../services/apiClient';
import { progressMessage, recommendationLabel } from '../services/childPersonalization';
import { comparisonRows, dedupeRecommendations, domainLabel, formatPercent } from './dashboardUI';
import { ModalitySummaryCard } from './ModalitySummaryCard';

export function ParentDashboard() {
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
					.getPersonalizationRecommendations(childId)
					.then(recommendations =>
						api.getPersonalizationProgress(childId).then(progress => setPersonalization({ profile, recommendations, progress })),
					)
					.catch(() => setPersonalization({ profile, recommendations: null, progress: null })),
			)
			.catch(() => setPersonalization({ profile: null, recommendations: null, progress: null }));
	}, []);

	const hasObservedData = Boolean(profile?.observations.length);
	const observedDomains = profile && Object.keys(profile.domains).length ? Object.entries(profile.domains).map(([domain, value]) => ({ label: domainLabel(domain), accuracy: value.accuracy })) : [];
	const recommendations = personalization.recommendations ? dedupeRecommendations(personalization.recommendations.recommendations) : [];
	const progressRows = comparisonRows(personalization.progress);
	const progressNote = progressMessage(personalization.progress);

	return (
		<div className="parent-space">
			<div className="parent-topline">
				<span className="eyebrow">Parent space {profile ? `· ${profile.mode} mode` : '· Research mode'}</span>
				<Link className="text-link" to="/">Back to Dyscover <span>↗</span></Link>
			</div>
			<PageHeader eyebrow="Good morning, Alex's parent" title="A quiet place to see what was observed.">
				<p className="page-lede">Observed activity data is shown carefully and never treated as a diagnosis.</p>
			</PageHeader>
			<div className="dashboard">
				<Card className="wide parent-welcome">
					<div>
						<Badge>{profile ? 'Latest screening profile' : 'Ready to explore'}</Badge>
						<h2>{profile ? 'Here is what the activity recorded.' : 'The map is ready when you are.'}</h2>
						<p>{profile ? 'This research-mode profile contains structured observations from completed activities.' : 'Start with a playful session, then return here to explore what was observed.'}</p>
						<Link className="button" to="/child/home">{profile ? 'Run another session' : 'Start a session'} <span>→</span></Link>
					</div>
					<div className="dashboard-map"><span>✦</span><span>✦</span><span>✦</span><span>✦</span><i /></div>
				</Card>

				<Card>
					<div className="card-title-row"><h3>Assessment profile</h3><span className="soft-icon">◌</span></div>
					{loading ? (
						<EmptyState>Loading observed activity data...</EmptyState>
					) : hasObservedData ? (
						<div className="observed-list">{profile?.observations.map(observation => <p key={observation}>{observation}</p>)}</div>
					) : (
						<EmptyState><strong>No completed profile yet.</strong><br />The first Dyscover adventure will appear here.</EmptyState>
					)}
				</Card>

				<Card>
					<div className="card-title-row"><h3>Observed areas</h3><span className="soft-icon">✦</span></div>
					{observedDomains.length ? (
						<div className="domain-list">
							{observedDomains.map(({ label, accuracy }) => (
								<div key={label}><span>{label}</span><strong>Activity accuracy · {formatPercent(accuracy)}</strong></div>
							))}
						</div>
					) : (
						<div className="empty-profile"><span>--</span><p>No domain observations available yet.</p></div>
					)}
				</Card>

				<Card className="wide">
					<div className="card-title-row"><h3>Model status</h3><Badge>{profile?.model.status ?? 'Unavailable'}</Badge></div>
					<div className="notice">No validated ML model is registered. Activity observations remain available and are not converted into a clinical prediction.</div>
				</Card>

				<Card className="wide recommendation-card">
					<Mascot mood="happy" size="small" />
					<div>
						<div className="card-title-row"><h3>Practice suggestions</h3>{personalization.profile && <Badge>Stage 5 personalization</Badge>}</div>
						{recommendations.length ? (
							<div className="observed-list">
								{recommendations.map(rec => <p key={rec.reason}><strong>{rec.kind === 'neutral' ? 'A starting point' : recommendationLabel(rec)}</strong><br />{rec.reason}</p>)}
							</div>
						) : (
							<p className="notice">Activity suggestions will appear here once enough observations have been gathered.</p>
						)}
					</div>
				</Card>

				<Card className="wide recommendation-card">
					<Mascot mood="thinking" size="small" />
					<div>
						<div className="card-title-row"><h3>Progress</h3>{personalization.profile && <Badge>Cumulative</Badge>}</div>
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