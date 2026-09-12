import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { DEFAULT_LANGUAGE, resolveLanguage, STORAGE_KEY, type LanguageCode } from './languages';
import { messages as enMessages, type MessageKey } from './messages/en';
import { messages as taMessages } from './messages/ta';

const RESOURCES: Record<LanguageCode, Record<string, string>> = {
  en: enMessages as Record<string, string>,
  ta: { ...enMessages, ...taMessages },
};

export interface LanguageContextValue {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  t: (key: MessageKey | string, params?: Record<string, string | number>) => string;
  locale: string;
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

function readStoredLanguage(): LanguageCode {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  try {
    return resolveLanguage(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>(readStoredLanguage);

  const setLanguage = useCallback((next: LanguageCode) => {
    setLanguageState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage may be unavailable; in-memory language still applies.
    }
  }, []);

  const t = useCallback(
    (key: MessageKey | string, params?: Record<string, string | number>) => {
      const table = RESOURCES[language];
      const template = table[key] ?? enMessages[key as MessageKey] ?? String(key);
      return interpolate(template, params);
    },
    [language],
  );

  const value = useMemo<LanguageContextValue>(() => {
    const definition = RESOURCES[language] ? language : DEFAULT_LANGUAGE;
    const locale = definition === 'ta' ? 'ta-IN' : 'en-US';
    return { language, setLanguage, t, locale };
  }, [language, setLanguage, t]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage, t } = useLanguage();
  return (
    <label className={`language-switcher${compact ? ' language-switcher-compact' : ''}`}>
      {!compact && <span className="language-switcher-label">{t('lang.switchLabel')}</span>}
      <select
        value={language}
        onChange={(event) => setLanguage(event.target.value as LanguageCode)}
        aria-label={t('lang.switchAria')}
      >
        <option value="en">{t('lang.en')}</option>
        <option value="ta">{t('lang.ta')}</option>
      </select>
    </label>
  );
}