import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useLanguage } from '../l10n';

export function Button({
  children,
  secondary = false,
  className = '',
  type = 'button',
  ...props
}: { children: ReactNode; secondary?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={['button', secondary ? 'button-secondary' : '', className]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {children}
    </button>
  );
}
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}
export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return (
    <div
      className="progress-track"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
    >
      <span style={{ width: `${value}%` }} />
    </div>
  );
}
export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      {children}
    </header>
  );
}
export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}
export function LoadingState({ label }: { label?: string }) {
  const { t } = useLanguage();
  return (
    <div className="empty-state" role="status" aria-live="polite">
      <span className="loading-dot" aria-hidden="true" /> {label ?? t('common.loading')}
    </div>
  );
}
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useLanguage();
  return (
    <div className="empty-state error-state" role="alert">
      <p>{message ?? t('common.error')}</p>
      {onRetry && (
        <Button secondary onClick={onRetry}>
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
}

export function Mascot({
  mood = 'idle',
  size = 'medium',
  decorative = false,
}: {
  mood?: 'idle' | 'happy' | 'thinking' | 'excited';
  size?: 'small' | 'medium' | 'large';
  decorative?: boolean;
}) {
  const { t } = useLanguage();
  return (
    <div
      className={`mascot mascot-${size} mascot-${mood}`}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : t('common.mascotLabel')}
    >
      <span className="mascot-star mascot-star-one">✦</span>
      <span className="mascot-star mascot-star-two">✦</span>
      <div className="mascot-body">
        <span className="mascot-ear mascot-ear-left" />
        <span className="mascot-ear mascot-ear-right" />
        <span className="mascot-eye mascot-eye-left" />
        <span className="mascot-eye mascot-eye-right" />
        <span className="mascot-smile" />
      </div>
    </div>
  );
}

export function MascotBubble({
  children,
  mood = 'happy',
}: {
  children: ReactNode;
  mood?: 'idle' | 'happy' | 'thinking' | 'excited';
}) {
  return (
    <div className="mascot-bubble">
      <Mascot mood={mood} size="small" decorative />
      <p>{children}</p>
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-heading">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h2>{title}</h2>
      {children}
    </div>
  );
}

export function Input({ className = '', ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`.trim()} {...props} />;
}

const A11Y_KEY = 'dyscover-a11y-preferences';

interface A11yPreferences {
  textSize: string;
  readingStyle: string;
  reducedMotion: boolean;
}

function readPreferences(): A11yPreferences {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const defaults = {
    textSize: 'normal',
    readingStyle: 'default',
    reducedMotion: Boolean(prefersReduced),
  };
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(A11Y_KEY) ?? 'null'
    ) as Partial<A11yPreferences> | null;
    return { ...defaults, ...(stored ?? {}) };
  } catch {
    return defaults;
  }
}

export function AccessibilityPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLanguage();
  const [prefs, setPrefs] = useState<A11yPreferences>(readPreferences);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = document.documentElement.dataset;
    root.textSize = prefs.textSize;
    root.readingStyle = prefs.readingStyle;
    root.reducedMotion = String(prefs.reducedMotion);
    try {
      window.localStorage.setItem(A11Y_KEY, JSON.stringify(prefs));
    } catch {
      // Preferences still apply for this visit.
    }
  }, [prefs]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>('select, input, button')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="settings-popover" role="dialog" aria-label={t('a11y.title')} ref={panelRef}>
      <div className="settings-heading">
        <strong>{t('a11y.title')}</strong>
        <button className="icon-button" onClick={onClose} aria-label={t('a11y.close')}>
          ×
        </button>
      </div>
      <label className="setting-row">
        {t('a11y.textSize')}
        <select
          value={prefs.textSize}
          onChange={event => setPrefs(p => ({ ...p, textSize: event.target.value }))}
        >
          <option value="normal">{t('a11y.textNormal')}</option>
          <option value="large">{t('a11y.textLarge')}</option>
          <option value="xlarge">{t('a11y.textXLarge')}</option>
        </select>
      </label>
      <label className="setting-row">
        {t('a11y.readingStyle')}
        <select
          value={prefs.readingStyle}
          onChange={event => setPrefs(p => ({ ...p, readingStyle: event.target.value }))}
        >
          <option value="default">{t('a11y.styleDefault')}</option>
          <option value="friendly">{t('a11y.styleFriendly')}</option>
        </select>
      </label>
      <label className="setting-check">
        <input
          type="checkbox"
          checked={prefs.reducedMotion}
          onChange={event => setPrefs(p => ({ ...p, reducedMotion: event.target.checked }))}
        />{' '}
        {t('a11y.reduceMotion')}
      </label>
    </div>
  );
}

/** Accessible confirmation step used before destructive actions. */
export function ConfirmButton({
  label,
  confirmLabel,
  prompt,
  onConfirm,
  disabled,
}: {
  label: string;
  confirmLabel: string;
  prompt: string;
  onConfirm: () => void | Promise<void>;
  disabled?: boolean;
}) {
  const { t } = useLanguage();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!asking) {
    return (
      <Button
        secondary
        className="button-danger"
        disabled={disabled}
        onClick={() => setAsking(true)}
      >
        {label}
      </Button>
    );
  }
  return (
    <span className="confirm-inline" role="group" aria-label={prompt}>
      <span>{prompt}</span>
      <Button
        className="button-danger"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onConfirm();
          } finally {
            setBusy(false);
            setAsking(false);
          }
        }}
      >
        {confirmLabel}
      </Button>
      <Button secondary disabled={busy} onClick={() => setAsking(false)}>
        {t('common.cancel')}
      </Button>
    </span>
  );
}
