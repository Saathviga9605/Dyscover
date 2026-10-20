import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Input } from '../components/ui';
import { useLanguage } from '../l10n';
import { ApiError } from '../services/apiClient';
import { useAuth } from './AuthContext';
import { homePathFor } from './LoginPage';

const MIN_PASSWORD = 8;
const MAX_PASSWORD_BYTES = 72;

export function RegisterPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<'parent' | 'educator'>('parent');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError('');
    if (password !== confirmPassword) {
      setError(t('auth.passwordsDoNotMatch'));
      return;
    }
    if (password.length < MIN_PASSWORD) {
      setError(t('auth.passwordTooShort'));
      return;
    }
    if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
      setError(t('auth.passwordTooLong'));
      return;
    }
    setSubmitting(true);
    try {
      const user = await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        role,
      });
      navigate(homePathFor(user), { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) setError(t('auth.emailExists'));
      else if (err instanceof ApiError && err.status === 429) setError(t('auth.tooManyAttempts'));
      else if (err instanceof ApiError && err.status === 422) setError(t('auth.checkFields'));
      else setError(t('auth.registerFailed'));
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
          <h1>{t('auth.registerTitle')}</h1>
          <p>{t('auth.registerSubtitle')}</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}
          <div className="form-group">
            <label htmlFor="display_name">{t('auth.displayName')}</label>
            <Input
              id="display_name"
              value={displayName}
              onChange={event => setDisplayName(event.target.value)}
              placeholder={t('auth.displayNamePlaceholder')}
              required
              maxLength={120}
              autoComplete="name"
              disabled={submitting}
            />
          </div>
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
              minLength={MIN_PASSWORD}
              autoComplete="new-password"
              aria-describedby="password-hint"
              disabled={submitting}
            />
            <small id="password-hint" className="form-hint">
              {t('auth.passwordHint')}
            </small>
          </div>
          <div className="form-group">
            <label htmlFor="confirm_password">{t('auth.confirmPassword')}</label>
            <Input
              id="confirm_password"
              type="password"
              value={confirmPassword}
              onChange={event => setConfirmPassword(event.target.value)}
              placeholder={t('auth.confirmPasswordPlaceholder')}
              required
              autoComplete="new-password"
              disabled={submitting}
            />
          </div>
          <fieldset className="form-group role-fieldset">
            <legend>{t('auth.role')}</legend>
            <label className="radio-pill">
              <input
                type="radio"
                name="role"
                value="parent"
                checked={role === 'parent'}
                onChange={() => setRole('parent')}
                disabled={submitting}
              />
              {t('auth.roleParent')}
            </label>
            <label className="radio-pill">
              <input
                type="radio"
                name="role"
                value="educator"
                checked={role === 'educator'}
                onChange={() => setRole('educator')}
                disabled={submitting}
              />
              {t('auth.roleEducator')}
            </label>
          </fieldset>
          <Button type="submit" className="button-full" disabled={submitting}>
            {submitting ? t('auth.registering') : t('auth.registerButton')}
          </Button>
        </form>
        <p className="auth-footer">
          {t('auth.hasAccount')} <Link to="/login">{t('auth.loginLink')}</Link>
        </p>
      </Card>
    </div>
  );
}
