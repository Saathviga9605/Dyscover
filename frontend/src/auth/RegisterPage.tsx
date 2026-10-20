import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { Button, Card, Input, PageHeader } from '../components/ui';
import { useLanguage } from '../l10n';

export function RegisterPage() {
  const { t } = useLanguage();
  const { register, isLoading: authLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<'parent' | 'educator'>('parent');
  const [error, setError] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const effectiveConfirm = confirmPassword || password;
    if (password !== effectiveConfirm) {
      setError(t('auth.passwordsDoNotMatch'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.passwordTooShort'));
      return;
    }
    setIsLoading(true);
    try {
      await register(email, password, displayName, role);
      setIsSuccess(true);
    } catch (err: unknown) {
      const apiError = err as { status?: number; message?: string };
      if (apiError.status === 409) {
        setError(t('auth.emailExists'));
      } else {
        setError(apiError.message ?? t('auth.registerFailed'));
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
          <h1>{t('auth.registerTitle')}</h1>
          <p>{t('auth.registerSubtitle')}</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error" role="alert">{error}</div>}
          {isSuccess && <div className="auth-success" role="status">Registration successful</div>}
          <div className="form-group">
            <label htmlFor="display_name">{t('auth.displayName')}</label>
            <Input
              id="display_name"
              name="display_name"
              type="text"
              value={displayName}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDisplayName(e.target.value)}
              placeholder={t('auth.displayNamePlaceholder')}
              required
              autoComplete="name"
              disabled={isLoading}
            />
          </div>
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
              disabled={isLoading}
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
              autoComplete="new-password"
              minLength={8}
              disabled={isLoading}
            />
          </div>
          <div className="form-group">
            <label htmlFor="confirmPassword">{t('auth.confirmPassword')}</label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
              placeholder={t('auth.confirmPasswordPlaceholder')}
              required
              autoComplete="new-password"
              disabled={isLoading}
            />
          </div>
          <div className="form-group">
            <label>{t('auth.role')}</label>
            <div className="role-options">
              <label className="role-option">
                <input
                  type="radio"
                  name="role"
                  value="parent"
                  checked={role === 'parent'}
                  onChange={() => setRole('parent')}
                  disabled={isLoading}
                />
                <span>{t('auth.roleParent')}</span>
              </label>
              <label className="role-option">
                <input
                  type="radio"
                  name="role"
                  value="educator"
                  checked={role === 'educator'}
                  onChange={() => setRole('educator')}
                  disabled={isLoading}
                />
                <span>{t('auth.roleEducator')}</span>
              </label>
            </div>
          </div>
          <Button type="submit" className="button-full" disabled={isLoading}>
            {isLoading ? t('auth.registering') : t('auth.registerButton')}
          </Button>
        </form>
        <p className="auth-footer">
          {t('auth.hasAccount')} <Link to="/login">{t('auth.loginLink')}</Link>
        </p>
      </Card>
    </div>
  );
}