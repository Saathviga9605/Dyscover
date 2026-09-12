import { describe, expect, it } from 'vitest';
import {
  assessmentPlanFor,
  getStoredLanguage,
  getStoredLocale,
  isActivityAvailable,
  localeFor,
  practicePlanFor,
  resolveLanguage,
  speechAssessmentPlanFor,
} from './languages';

describe('language resolution', () => {
  it('falls back to English for unsupported values', () => {
    expect(resolveLanguage(null)).toBe('en');
    expect(resolveLanguage('fr')).toBe('en');
    expect(resolveLanguage(undefined)).toBe('en');
  });

  it('resolves supported language codes', () => {
    expect(resolveLanguage('en')).toBe('en');
    expect(resolveLanguage('ta')).toBe('ta');
  });

  it('maps codes to locales', () => {
    expect(localeFor('en')).toBe('en-US');
    expect(localeFor('ta')).toBe('ta-IN');
  });
});

describe('activity availability gating', () => {
  it('isActivityAvailable reflects language support', () => {
    expect(isActivityAvailable('mirror-match', 'en')).toBe(true);
    expect(isActivityAvailable('mirror-match', 'ta')).toBe(true);
    expect(isActivityAvailable('letter-detective', 'ta')).toBe(false);
    expect(isActivityAvailable('word-flash', 'ta')).toBe(false);
    expect(isActivityAvailable('sound-quest-adventure', 'ta')).toBe(false);
    expect(isActivityAvailable('symbol-match', 'ta')).toBe(true);
    expect(isActivityAvailable('symbol-match', 'en')).toBe(true);
    expect(isActivityAvailable('unknown-activity', 'en')).toBe(false);
  });
});

describe('plan gating', () => {
  it('assessmentPlanFor keeps only available games per language', () => {
    expect(assessmentPlanFor('en')).toEqual(['letter-detective', 'mirror-match', 'word-flash', 'sequence-quest', 'word-maze']);
    expect(assessmentPlanFor('ta')).toEqual(['mirror-match']);
  });

  it('speechAssessmentPlanFor is empty for Tamil', () => {
    expect(speechAssessmentPlanFor('en')).toEqual(['sound-quest-adventure', 'letter-bubble-pop', 'maze-runner-rush']);
    expect(speechAssessmentPlanFor('ta')).toEqual([]);
  });

  it('practicePlanFor narrows for Tamil', () => {
    expect(practicePlanFor('en')).toEqual(['symbol-match', 'word-builder', 'sequence-recall', 'visual-search']);
    expect(practicePlanFor('ta')).toEqual(['symbol-match']);
  });
});

describe('stored language', () => {
  it('returns the default when storage is unavailable', () => {
    expect(getStoredLanguage()).toBe('en');
    expect(getStoredLocale()).toBe('en-US');
  });
});