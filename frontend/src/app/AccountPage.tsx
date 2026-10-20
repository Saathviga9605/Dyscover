import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { Button, Card, ErrorState, Input, LoadingState, PageHeader } from '../components/ui';
import { useLanguage } from '../l10n';
import { api, ApiError, setAccessToken, type DataSummary } from '../services/apiClient';

function ChangePasswordCard() {
  const { t } = useLanguage();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [status, setStatus] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  return (
    <Card>
      <h3>{t('account.passwordTitle')}</h3>
      <form
        className="auth-form"
        onSubmit={async event => {
          event.preventDefault();
          if (saving) return;
          if (next.length < 8) {
            setStatus({ kind: 'error', text: t('auth.passwordTooShort') });
            return;
          }
          setSaving(true);
          setStatus(null);
          try {
            const tokens = await api.changePassword({
              current_password: current,
              new_password: next,
            });
            setAccessToken(tokens.access_token);
            setCurrent('');
            setNext('');
            setStatus({ kind: 'ok', text: t('account.passwordChanged') });
          } catch (err) {
            setStatus({
              kind: 'error',
              text:
                err instanceof ApiError && err.status === 400
                  ? err.message
                  : t('account.passwordError'),
            });
          } finally {
            setSaving(false);
          }
        }}
      >
        <div className="form-group">
          <label htmlFor="current_password">{t('account.currentPassword')}</label>
          <Input
            id="current_password"
            type="password"
            value={current}
            onChange={e => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        <div className="form-group">
          <label htmlFor="new_password">{t('account.newPassword')}</label>
          <Input
            id="new_password"
            type="password"
            value={next}
            onChange={e => setNext(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          <small className="form-hint">{t('account.passwordSessionsNote')}</small>
        </div>
        {status && (
          <p
            className={status.kind === 'ok' ? 'auth-success' : 'auth-error'}
            role={status.kind === 'ok' ? 'status' : 'alert'}
          >
            {status.text}
          </p>
        )}
        <Button type="submit" disabled={saving}>
          {t('account.passwordSave')}
        </Button>
      </form>
    </Card>
  );
}

function DataCard() {
  const { t } = useLanguage();
  const [summary, setSummary] = useState<DataSummary | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const load = () => {
    setState('loading');
    api
      .getDataSummary()
      .then(value => {
        setSummary(value);
        setState('ready');
      })
      .catch(() => setState('error'));
  };
  useEffect(load, []);

  return (
    <Card className="wide">
      <h3>{t('account.dataTitle')}</h3>
      {state === 'loading' ? (
        <LoadingState />
      ) : state === 'error' || !summary ? (
        <ErrorState onRetry={load} />
      ) : (
        <>
          <dl className="domain-list">
            <div>
              <dt>{t('account.dataChildren')}</dt>
              <dd>{summary.children.count}</dd>
            </div>
            <div>
              <dt>{t('account.dataAssessments')}</dt>
              <dd>{summary.assessments.count}</dd>
            </div>
            <div>
              <dt>{t('account.dataTrials')}</dt>
              <dd>{summary.trials.count}</dd>
            </div>
            <div>
              <dt>{t('account.dataPractice')}</dt>
              <dd>{summary.practice_sessions.count}</dd>
            </div>
            <div>
              <dt>{t('account.dataSpeech')}</dt>
              <dd>{summary.speech_sessions.count}</dd>
            </div>
            <div>
              <dt>{t('account.dataLexi')}</dt>
              <dd>{summary.lexi_conversations.count}</dd>
            </div>
          </dl>
          <p className="notice">{t('account.retention')}</p>
        </>
      )}
      <div className="card-actions">
        <Button
          secondary
          disabled={exporting}
          onClick={async () => {
            setExporting(true);
            setExportError('');
            try {
              const blob = await api.exportData();
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `dyscover-export-${new Date().toISOString().slice(0, 10)}.zip`;
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            } catch {
              setExportError(t('account.exportError'));
            } finally {
              setExporting(false);
            }
          }}
        >
          {exporting ? t('account.exporting') : t('account.export')}
        </Button>
        {exportError && (
          <span className="auth-error" role="alert">
            {exportError}
          </span>
        )}
      </div>
    </Card>
  );
}

function DangerCard() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { clearSession } = useAuth();
  const [password, setPassword] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const confirmWord = t('account.deleteWord');

  return (
    <Card className="wide danger-card">
      <h3>{t('account.sessionsTitle')}</h3>
      <p>{t('account.sessionsCopy')}</p>
      <Button
        secondary
        onClick={async () => {
          await api.logoutEverywhere().catch(() => undefined);
          clearSession();
          window.location.replace('/login');
        }}
      >
        {t('account.logoutEverywhere')}
      </Button>
      <hr />
      <h3>{t('account.deleteTitle')}</h3>
      <p>{t('account.deleteCopy')}</p>
      <form
        className="auth-form"
        onSubmit={async event => {
          event.preventDefault();
          if (busy || confirmText.trim().toUpperCase() !== confirmWord.toUpperCase()) return;
          setBusy(true);
          setError('');
          try {
            await api.deleteAccount(password);
            clearSession();
            // Full navigation: drops every in-memory trace of the deleted account and
            // avoids the route guard redirecting to login mid-transition.
            window.location.replace('/');
          } catch (err) {
            setError(
              err instanceof ApiError && err.status === 400
                ? t('account.deleteWrongPassword')
                : t('account.deleteError')
            );
            setBusy(false);
          }
        }}
      >
        <div className="form-group">
          <label htmlFor="delete_password">{t('auth.password')}</label>
          <Input
            id="delete_password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        <div className="form-group">
          <label htmlFor="delete_confirm">
            {t('account.deleteTypeWord', { word: confirmWord })}
          </label>
          <Input
            id="delete_confirm"
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            required
            autoComplete="off"
          />
        </div>
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
        <Button
          type="submit"
          className="button-danger"
          disabled={
            busy || !password || confirmText.trim().toUpperCase() !== confirmWord.toUpperCase()
          }
        >
          {busy ? t('account.deleting') : t('account.deleteButton')}
        </Button>
      </form>
    </Card>
  );
}

export function AccountPage() {
  const { t } = useLanguage();
  const { user } = useAuth();
  if (!user) return <LoadingState />;
  return (
    <div className="parent-space">
      <PageHeader eyebrow={t('account.eyebrow')} title={t('account.title')}>
        <p className="page-lede">
          {user.display_name} · {user.email} ·{' '}
          {t(`auth.role${user.role === 'educator' ? 'Educator' : 'Parent'}`)}
        </p>
      </PageHeader>
      <div className="dashboard">
        <ChangePasswordCard />
        <Card>
          <h3>{t('account.privacyTitle')}</h3>
          <p>{t('account.privacyCopy')}</p>
          <ul className="plain-list">
            <li>{t('account.privacyGaze')}</li>
            <li>{t('account.privacySpeech')}</li>
            <li>{t('account.privacyLexi')}</li>
          </ul>
        </Card>
        {user.role === 'parent' && <DataCard />}
        <DangerCard />
      </div>
    </div>
  );
}
