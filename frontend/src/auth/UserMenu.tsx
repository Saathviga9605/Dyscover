import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { useLanguage } from '../l10n';

export function UserMenu() {
  const { t } = useLanguage();
  const { user, isAuthenticated, logout } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    setUserMenuOpen(false);
  };

  if (!isAuthenticated) {
    return (
      <>
        <Link className="nav-link" to="/login" onClick={() => setMenuOpen(false)}>
          {t('auth.loginNav')}
        </Link>
        <Link className="nav-cta" to="/register" onClick={() => setMenuOpen(false)}>
          {t('auth.registerNav')} <span>✦</span>
        </Link>
      </>
    );
  }

  return (
    <div className="user-menu" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <span className="user-greeting">Welcome{user?.display_name ? `, ${user.display_name}` : ''}</span>
      <button className="button-secondary button-small" onClick={handleLogout} aria-label={t('auth.logout')}>
        {t('auth.logout')}
      </button>
    </div>
  );
}