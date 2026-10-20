import type { ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { Card, LoadingState, Mascot } from '../components/ui';
import { useLanguage } from '../l10n';
import type { UserRole } from '../services/apiClient';
import { useAuth } from './AuthContext';

/**
 * Client-side route guard. It only shapes the UI; every API call is authorized
 * by the server regardless of what this component renders.
 */
export function RequireAuth({ roles, children }: { roles?: UserRole[]; children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  const { t } = useLanguage();

  if (isLoading) return <LoadingState />;
  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="auth-page">
        <Card className="auth-card">
          <div className="auth-header">
            <Mascot mood="thinking" size="small" />
            <h1>{t('guard.wrongRoleTitle')}</h1>
            <p>{t('guard.wrongRoleCopy')}</p>
          </div>
          <Link
            className="button"
            to={user.role === 'educator' ? '/educator/dashboard' : '/parent/dashboard'}
          >
            {t('guard.goToMySpace')} <span aria-hidden="true">→</span>
          </Link>
        </Card>
      </div>
    );
  }
  return <>{children}</>;
}

/** Only allow same-site relative redirect targets (prevents open redirects). */
export function safeNextPath(raw: string | null, fallback: string): string {
  if (!raw) return fallback;
  try {
    const decoded = decodeURIComponent(raw);
    return decoded.startsWith('/') && !decoded.startsWith('//') ? decoded : fallback;
  } catch {
    return fallback;
  }
}
