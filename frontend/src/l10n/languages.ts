export type LanguageCode = 'en' | 'ta';

export interface LanguageDefinition {
  code: LanguageCode;
  name: string;
  nativeName: string;
  locale: string;
  default: boolean;
}

export const DEFAULT_LANGUAGE: LanguageCode = 'en';
export const CONTENT_VERSION = '1.0';
export const STORAGE_KEY = 'dyscover-stage2-language';

export const LANGUAGES: LanguageDefinition[] = [
  { code: 'en', name: 'English', nativeName: 'English', locale: 'en-US', default: true },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', locale: 'ta-IN', default: false },
];

const SUPPORTED_LANGUAGES = new Set<string>(LANGUAGES.map((language) => language.code));

const ASSESSMENT_ACTIVITIES: Record<string, ReadonlySet<string>> = {
  'letter-detective': new Set(['en']),
  'mirror-match': new Set(['en', 'ta']),
  'word-flash': new Set(['en']),
  'sequence-quest': new Set(['en']),
  'word-maze': new Set(['en']),
  'sound-quest-adventure': new Set(['en']),
  'letter-bubble-pop': new Set(['en']),
  'maze-runner-rush': new Set(['en']),
};

const PRACTICE_ACTIVITIES: Record<string, ReadonlySet<string>> = {
  'symbol-match': new Set(['en', 'ta']),
  'word-builder': new Set(['en']),
  'sequence-recall': new Set(['en']),
  'visual-search': new Set(['en']),
  'sound-quest': new Set(['en']),
  'letter-pop': new Set(['en']),
  'maze-ran': new Set(['en']),
};

const ACTIVITY_LANGUAGES: Record<string, ReadonlySet<string>> = {
  ...ASSESSMENT_ACTIVITIES,
  ...PRACTICE_ACTIVITIES,
};

const ASSESSMENT_PLAN: string[] = ['letter-detective', 'mirror-match', 'word-flash', 'sequence-quest', 'word-maze'];
const SPEECH_ASSESSMENT_PLAN: string[] = ['sound-quest-adventure', 'letter-bubble-pop', 'maze-runner-rush'];
const PRACTICE_PLAN: string[] = ['symbol-match', 'word-builder', 'sequence-recall', 'visual-search'];

export function isSupported(value: string | null | undefined): value is LanguageCode {
  return typeof value === 'string' && SUPPORTED_LANGUAGES.has(value);
}

export function resolveLanguage(value: string | null | undefined): LanguageCode {
  return isSupported(value) ? value : DEFAULT_LANGUAGE;
}

export function localeFor(value: string | null | undefined): string {
  const resolved = resolveLanguage(value);
  return LANGUAGES.find((language) => language.code === resolved)?.locale ?? LANGUAGES[0].locale;
}

export function languageName(value: LanguageCode): string {
  return LANGUAGES.find((language) => language.code === value)?.name ?? DEFAULT_LANGUAGE;
}

export function languageNativeName(value: LanguageCode): string {
  return LANGUAGES.find((language) => language.code === value)?.nativeName ?? nativeLanguageName(DEFAULT_LANGUAGE);
}

function nativeLanguageName(value: LanguageCode): string {
  return LANGUAGES.find((language) => language.code === value)?.nativeName ?? 'English';
}

export function isActivityAvailable(activityId: string, language: LanguageCode): boolean {
  const languages = ACTIVITY_LANGUAGES[activityId];
  return languages ? languages.has(language) : false;
}

export function activitiesFor(language: LanguageCode): string[] {
  return Object.entries(ACTIVITY_LANGUAGES)
    .filter(([, languages]) => languages.has(language))
    .map(([activityId]) => activityId);
}

export function languagesForActivity(activityId: string): string[] {
  return [...(ACTIVITY_LANGUAGES[activityId] ?? [])].sort();
}

export function assessmentPlanFor(language: LanguageCode): string[] {
  return ASSESSMENT_PLAN.filter((gameId) => isActivityAvailable(gameId, language));
}

export function speechAssessmentPlanFor(language: LanguageCode): string[] {
  return SPEECH_ASSESSMENT_PLAN.filter((gameId) => isActivityAvailable(gameId, language));
}

export function practicePlanFor(language: LanguageCode): string[] {
  return PRACTICE_PLAN.filter((activityId) => isActivityAvailable(activityId, language));
}

export function getStoredLanguage(): LanguageCode {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  try {
    return resolveLanguage(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

export function getStoredLocale(): string {
  return localeFor(getStoredLanguage());
}