import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Card, ErrorState, LoadingState, Mascot } from '../components/ui';
import { useLanguage } from '../l10n';
import { useChildren } from './ChildContext';

/** Child activities only run for a child profile the adult has selected. */
export function RequireChild({ children: content }: { children: ReactNode }) {
  const { t } = useLanguage();
  const { children, activeChild, selectChild, loaded, error, reload } = useChildren();

  if (activeChild) return <>{content}</>;
  if (error && !loaded) return <ErrorState onRetry={reload} />;
  if (!loaded) return <LoadingState />;

  return (
    <div className="child-space">
      <Card className="auth-card child-picker">
        <Mascot mood="happy" size="medium" />
        <h1>{children.length ? t('picker.title') : t('picker.noneTitle')}</h1>
        <p>{children.length ? t('picker.copy') : t('picker.noneCopy')}</p>
        {children.length ? (
          <div className="child-picker-grid">
            {children.map(child => (
              <button
                key={child.id}
                type="button"
                className="child-picker-button"
                onClick={() => selectChild(child.id)}
              >
                <span className="child-avatar" aria-hidden="true">
                  {child.display_name.slice(0, 1).toUpperCase()}
                </span>
                {child.display_name}
              </button>
            ))}
          </div>
        ) : (
          <Link className="button button-sun" to="/parent/dashboard">
            {t('picker.addChild')} <span aria-hidden="true">→</span>
          </Link>
        )}
      </Card>
    </div>
  );
}
