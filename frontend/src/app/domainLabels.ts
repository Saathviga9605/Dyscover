import { useCallback } from 'react';
import { useLanguage } from '../l10n';
import { domainLabel } from './dashboardUI';

/** Localized label for an assessment domain, falling back to the English label. */
export function useDomainLabel(): (domain: string | null | undefined) => string {
  const { t } = useLanguage();
  return useCallback(
    (domain: string | null | undefined) => {
      if (!domain) return '';
      const key = `domain.${domain}`;
      const translated = t(key);
      return translated === key ? domainLabel(domain) : translated;
    },
    [t]
  );
}
