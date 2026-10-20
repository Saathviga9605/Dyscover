import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  Mascot,
  PageHeader,
} from '../components/ui';
import { PracticeCard } from '../games/practice/PracticeCard';
import { useLanguage } from '../l10n';
import {
  api,
  ApiError,
  type ChildProfile,
  type EducatorGrant,
  type PersonalizationRecommendations,
  type ProgressResponse,
} from '../services/apiClient';
import { progressMessage, recommendationLabel } from '../services/childPersonalization';
import { useChildren } from './ChildContext';
import { comparisonRows, dedupeRecommendations, formatPercent } from './dashboardUI';
import { useDomainLabel } from './domainLabels';
import { ModalitySummaryCard } from './ModalitySummaryCard';

type Profile = Awaited<ReturnType<typeof api.getProfile>>;

const CURRENT_YEAR = new Date().getFullYear();

function AddChildForm({
  onCreated,
  onCancel,
}: {
  onCreated: (child: ChildProfile) => void;
  onCancel?: () => void;
}) {
  const { t } = useLanguage();
  const [name, setName] = useState('');
  const [birthYear, setBirthYear] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  return (
    <form
      className="add-child-form"
      onSubmit={async event => {
        event.preventDefault();
        if (saving || !name.trim()) return;
        setSaving(true);
        setError('');
        try {
          const created = await api.createChild({
            display_name: name.trim(),
            birth_year: birthYear ? Number.parseInt(birthYear, 10) : undefined,
          });
          setName('');
          setBirthYear('');
          onCreated(created);
        } catch (err) {
          setError(
            err instanceof ApiError && err.status === 422
              ? t('children.invalid')
              : t('children.createError')
          );
        } finally {
          setSaving(false);
        }
      }}
    >
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-group">
        <label htmlFor="child_name">{t('children.nameLabel')}</label>
        <Input
          id="child_name"
          value={name}
          onChange={event => setName(event.target.value)}
          placeholder={t('children.namePlaceholder')}
          maxLength={80}
          required
          autoComplete="off"
        />
        <small className="form-hint">{t('children.nameHint')}</small>
      </div>
      <div className="form-group">
        <label htmlFor="child_birth_year">{t('children.birthYearLabel')}</label>
        <Input
          id="child_birth_year"
          type="number"
          inputMode="numeric"
          value={birthYear}
          onChange={event => setBirthYear(event.target.value)}
          min={2010}
          max={Math.min(2030, CURRENT_YEAR)}
        />
      </div>
      <div className="form-actions">
        <Button type="submit" disabled={saving || !name.trim()}>
          {saving ? t('children.saving') : t('children.create')}
        </Button>
        {onCancel && (
          <Button secondary onClick={onCancel}>
            {t('common.cancel')}
          </Button>
        )}
      </div>
    </form>
  );
}

function ChildrenCard() {
  const { t } = useLanguage();
  const { children, activeChild, selectChild, reload, loaded, error } = useChildren();
  const [adding, setAdding] = useState(false);

  if (!loaded && !error)
    return (
      <Card className="wide">
        <LoadingState />
      </Card>
    );
  if (error && !loaded)
    return (
      <Card className="wide">
        <ErrorState onRetry={reload} />
      </Card>
    );

  return (
    <Card className="wide child-profiles-card">
      <div className="card-title-row">
        <h2 className="card-heading">{t('children.title')}</h2>
        {children.length > 0 && !adding && (
          <Button secondary className="button-small" onClick={() => setAdding(true)}>
            {t('children.add')}
          </Button>
        )}
      </div>
      {children.length === 0 ? (
        <>
          <p>{t('children.emptyCopy')}</p>
          <AddChildForm
            onCreated={async created => {
              await reload();
              selectChild(created.id);
            }}
          />
        </>
      ) : (
        <>
          <ul className="child-list">
            {children.map(child => {
              const selected = child.id === activeChild?.id;
              return (
                <li key={child.id} className={selected ? 'selected' : ''}>
                  <button
                    type="button"
                    className="child-select"
                    aria-pressed={selected}
                    onClick={() => selectChild(child.id)}
                  >
                    <span className="child-avatar" aria-hidden="true">
                      {child.display_name.slice(0, 1).toUpperCase()}
                    </span>
                    <span>
                      <strong>{child.display_name}</strong>
                      {child.birth_year ? <small> · {child.birth_year}</small> : null}
                    </span>
                    {selected && <Badge>{t('children.selected')}</Badge>}
                  </button>
                  <ConfirmButton
                    label={t('children.delete')}
                    confirmLabel={t('children.deleteConfirm')}
                    prompt={t('children.deletePrompt', { name: child.display_name })}
                    onConfirm={async () => {
                      await api.deleteChild(child.id);
                      if (selected) selectChild(null);
                      await reload();
                    }}
                  />
                </li>
              );
            })}
          </ul>
          {adding && (
            <AddChildForm
              onCreated={async created => {
                setAdding(false);
                await reload();
                selectChild(created.id);
              }}
              onCancel={() => setAdding(false)}
            />
          )}
        </>
      )}
    </Card>
  );
}

function SharingCard({ child }: { child: ChildProfile }) {
  const { t } = useLanguage();
  const [grants, setGrants] = useState<EducatorGrant[] | null>(null);
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<{ kind: 'error' | 'ok'; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api
      .listEducatorGrants(child.id)
      .then(setGrants)
      .catch(() => setGrants([]));
  }, [child.id]);
  useEffect(load, [load]);

  return (
    <Card className="wide">
      <div className="card-title-row">
        <h3>{t('sharing.title')}</h3>
      </div>
      <p className="subtle-text">{t('sharing.copy')}</p>
      {grants === null ? (
        <LoadingState />
      ) : grants.length ? (
        <ul className="grant-list">
          {grants.map(grant => (
            <li key={grant.educator_id}>
              <span>{grant.educator_display_name ?? t('sharing.unnamedEducator')}</span>
              <ConfirmButton
                label={t('sharing.revoke')}
                confirmLabel={t('sharing.revokeConfirm')}
                prompt={t('sharing.revokePrompt')}
                onConfirm={async () => {
                  await api.revokeEducator(child.id, grant.educator_id);
                  load();
                }}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="notice">{t('sharing.none')}</p>
      )}
      <form
        className="inline-form"
        onSubmit={async event => {
          event.preventDefault();
          if (saving || !email.trim()) return;
          setSaving(true);
          setMessage(null);
          try {
            await api.grantEducator(child.id, email.trim());
            setEmail('');
            setMessage({ kind: 'ok', text: t('sharing.granted') });
            load();
          } catch (err) {
            setMessage({
              kind: 'error',
              text:
                err instanceof ApiError && err.status === 404
                  ? t('sharing.notFound')
                  : t('sharing.error'),
            });
          } finally {
            setSaving(false);
          }
        }}
      >
        <label htmlFor="educator_email">{t('sharing.emailLabel')}</label>
        <div className="inline-form-row">
          <Input
            id="educator_email"
            type="email"
            value={email}
            onChange={event => setEmail(event.target.value)}
            placeholder={t('sharing.emailPlaceholder')}
            required
            autoComplete="off"
          />
          <Button type="submit" disabled={saving || !email.trim()}>
            {t('sharing.grant')}
          </Button>
        </div>
        {message && (
          <p
            className={message.kind === 'error' ? 'auth-error' : 'auth-success'}
            role={message.kind === 'error' ? 'alert' : 'status'}
          >
            {message.text}
          </p>
        )}
      </form>
    </Card>
  );
}

function ChildObservations({ child }: { child: ChildProfile }) {
  const { t, language } = useLanguage();
  const domainLabel = useDomainLabel();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [profileState, setProfileState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [recommendations, setRecommendations] = useState<PersonalizationRecommendations | null>(
    null
  );
  const [progress, setProgress] = useState<ProgressResponse | null>(null);

  useEffect(() => {
    let active = true;
    setProfileState('loading');
    api
      .listAssessments(child.id, 10)
      .then(assessments => {
        const latest = assessments.find(item => item.status === 'completed') ?? assessments[0];
        if (active) setAssessmentId(latest?.id ?? null);
        return latest ? api.getProfile(latest.id) : null;
      })
      .then(value => {
        if (!active) return;
        setProfile(value);
        setProfileState('ready');
      })
      .catch(() => active && setProfileState('error'));
    return () => {
      active = false;
    };
  }, [child.id]);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getPersonalizationRecommendations(child.id, language).catch(() => null),
      api.getPersonalizationProgress(child.id).catch(() => null),
    ]).then(([recs, prog]) => {
      if (!active) return;
      setRecommendations(recs);
      setProgress(prog);
    });
    return () => {
      active = false;
    };
  }, [child.id, language]);

  const observedDomains = profile ? Object.entries(profile.domains) : [];
  const recs = recommendations ? dedupeRecommendations(recommendations.recommendations) : [];
  const progressRows = comparisonRows(progress);

  return (
    <>
      <Card className="wide parent-welcome">
        <div>
          <Badge>{t('parent.forChild', { name: child.display_name })}</Badge>
          <h2>{profile ? t('parent.welcomeTitle') : t('parent.welcomeReadyTitle')}</h2>
          <p>{profile ? t('parent.welcomeCopy') : t('parent.welcomeReadyCopy')}</p>
          <Link className="button button-sun" to="/child/home">
            {profile ? t('parent.runAnother') : t('parent.startSession')}{' '}
            <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="dashboard-map" aria-hidden="true">
          <span>✦</span>
          <span>✦</span>
          <span>✦</span>
          <span>✦</span>
          <i />
        </div>
      </Card>

      <Card>
        <div className="card-title-row">
          <h3>{t('parent.profileCard')}</h3>
        </div>
        {profileState === 'loading' ? (
          <LoadingState label={t('parent.loading')} />
        ) : profileState === 'error' ? (
          <ErrorState />
        ) : profile?.observations.length ? (
          <div className="observed-list">
            {profile.observations.map(observation => (
              <p key={observation}>{observation}</p>
            ))}
          </div>
        ) : (
          <EmptyState>
            <strong>{t('parent.noProfileYet')}</strong>
            <br />
            {t('parent.noProfileHint')}
          </EmptyState>
        )}
      </Card>

      <Card>
        <div className="card-title-row">
          <h3>{t('parent.observedTitle')}</h3>
        </div>
        {observedDomains.length ? (
          <dl className="domain-list">
            {observedDomains.map(([domain, value]) => (
              <div key={domain}>
                <dt>{domainLabel(domain)}</dt>
                <dd>
                  {typeof value.accuracy === 'number'
                    ? t('parent.accuracyFormat', { percent: formatPercent(value.accuracy) })
                    : t('parent.notEnoughEvidence')}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="notice">{t('parent.noDomains')}</p>
        )}
      </Card>

      <Card className="wide">
        <div className="card-title-row">
          <h3>{t('parent.modelStatus')}</h3>
          <Badge>{t('parent.modelUnavailable')}</Badge>
        </div>
        <div className="notice">{t('parent.modelNotice')}</div>
      </Card>

      <Card className="wide recommendation-card">
        <Mascot mood="happy" size="small" decorative />
        <div>
          <div className="card-title-row">
            <h3>{t('parent.suggestionsTitle')}</h3>
            <Badge>{t('parent.suggestionBadge')}</Badge>
          </div>
          {recs.length ? (
            <div className="observed-list">
              {recs.map(rec => (
                <p key={`${rec.kind}-${rec.target_domain ?? 'none'}-${rec.game_id ?? ''}`}>
                  <strong>
                    {rec.kind === 'neutral' ? t('parent.startingPoint') : recommendationLabel(rec)}
                  </strong>
                  <br />
                  {rec.reason}
                </p>
              ))}
            </div>
          ) : (
            <p className="notice">{t('parent.suggestionsNone')}</p>
          )}
        </div>
      </Card>

      <Card className="wide recommendation-card">
        <Mascot mood="thinking" size="small" decorative />
        <div>
          <div className="card-title-row">
            <h3>{t('parent.progressTitle')}</h3>
          </div>
          {progressRows.length ? (
            <dl className="domain-list">
              {progressRows.map(row => (
                <div key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>{row.deltaText}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="notice">{progressMessage(progress)}</p>
          )}
        </div>
      </Card>

      <ModalitySummaryCard
        dataQuality={profile?.data_quality ?? null}
        assessmentId={assessmentId}
      />
      <PracticeCard />
      <SharingCard child={child} />
    </>
  );
}

export function ParentDashboard() {
  const { t } = useLanguage();
  const { activeChild, children } = useChildren();

  return (
    <div className="parent-space">
      <PageHeader eyebrow={t('parent.headerEyebrow')} title={t('parent.headerTitle')}>
        <p className="page-lede">{t('parent.headerLede')}</p>
      </PageHeader>
      <div className="dashboard">
        <ChildrenCard />
        {activeChild ? (
          <ChildObservations key={activeChild.id} child={activeChild} />
        ) : children.length ? (
          <Card className="wide">
            <EmptyState>{t('children.pickOne')}</EmptyState>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

export default ParentDashboard;
