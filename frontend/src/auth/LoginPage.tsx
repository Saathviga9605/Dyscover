import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Card, Input } from '../components/ui';
import { useLanguage } from '../l10n';
import { ApiError, type CurrentUser } from '../services/apiClient';
import { useAuth } from './AuthContext';
import { safeNextPath } from './RequireAuth';

export function homePathFor(user: CurrentUser): string {
  return user.role === 'educator' ? '/educator/dashboard' : '/parent/dashboard';
}

export function LoginPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError('');
    setSubmitting(true);
    try {
      const user = await login(email.trim(), password);
      navigate(safeNextPath(params.get('next'), homePathFor(user)), { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) setError(t('auth.invalidCredentials'));
      else if (err instanceof ApiError && err.status === 429) setError(t('auth.tooManyAttempts'));
      else if (err instanceof ApiError && err.code === 'network') setError(t('common.offline'));
      else setError(t('auth.loginFailed'));
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <div className="auth-header">
          <span className="brand-mark" aria-hidden="true">
            ✦
          </span>
          <h1>{t('auth.loginTitle')}</h1>
          <p>{t('auth.loginSubtitle')}</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form" noValidate={false}>
          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}
          <div className="form-group">
            <label htmlFor="email">{t('auth.email')}</label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder={t('auth.emailPlaceholder')}
              required
              autoComplete="email"
              disabled={submitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              placeholder={t('auth.passwordPlaceholder')}
              required
              autoComplete="current-password"
              disabled={submitting}
            />
          </div>
          <Button type="submit" className="button-full" disabled={submitting}>
            {submitting ? t('auth.loggingIn') : t('auth.loginButton')}
          </Button>
        </form>
        <p className="auth-footer">
          {t('auth.noAccount')} <Link to="/register">{t('auth.registerLink')}</Link>
        </p>
      </Card>
    </div>
  );
}
