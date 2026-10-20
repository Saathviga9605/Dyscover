import { Link, useNavigate } from 'react-router-dom';
import { useLanguage } from '../l10n';
import { useAuth } from './AuthContext';

export function UserMenu({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  if (isLoading) return null;
  if (!isAuthenticated || !user) {
    return (
      <>
        <Link className="nav-link" to="/login" onClick={onNavigate}>
          {t('auth.loginNav')}
        </Link>
        <Link className="nav-cta" to="/register" onClick={onNavigate}>
          {t('auth.registerNav')} <span aria-hidden="true">✦</span>
        </Link>
      </>
    );
  }

  return (
    <div className="user-menu">
      <Link className="user-greeting" to="/account" onClick={onNavigate}>
        {t('auth.account', { name: user.display_name || user.email })}
      </Link>
      <button
        type="button"
        className="button button-secondary button-small"
        onClick={async () => {
          onNavigate?.();
          await logout();
          navigate('/', { replace: true });
        }}
      >
        {t('auth.logout')}
      </button>
    </div>
  );
}
