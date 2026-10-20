import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { Button, Card, Input, PageHeader } from '../components/ui';
import { useLanguage } from '../l10n';

export function LoginPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { login, isLoading: authLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login(email, password);
      navigate('/parent/dashboard');
    } catch (err: unknown) {
      const apiError = err as { status?: number; message?: string };
      if (apiError.status === 401) {
        setError(t('auth.invalidCredentials'));
      } else if (apiError.status === 403) {
        setError(t('auth.accountInactive'));
      } else {
        setError(apiError.message ?? t('auth.loginFailed'));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <div className="auth-header">
          <span className="brand-mark">✦</span>
          <h1>{t('auth.loginTitle')}</h1>
          <p>{t('auth.loginSubtitle')}</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error" role="alert">{error}</div>}
          <div className="form-group">
            <label htmlFor="email">{t('auth.email')}</label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
              placeholder={t('auth.emailPlaceholder')}
              required
              autoComplete="email"
              disabled={isLoading || authLoading}
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              placeholder={t('auth.passwordPlaceholder')}
              required
              autoComplete="current-password"
              disabled={isLoading || authLoading}
            />
          </div>
          <Button type="submit" className="button-full" disabled={isLoading || authLoading}>
            {isLoading || authLoading ? t('auth.loggingIn') : t('auth.loginButton')}
          </Button>
        </form>
        <p className="auth-footer">
          {t('auth.noAccount')} <Link to="/register">{t('auth.registerLink')}</Link>
        </p>
      </Card>
    </div>
  );
}