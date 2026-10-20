/**
 * Which child profile the signed-in adult is currently playing as.
 *
 * Only the profile *id* is remembered on this device, as a convenience. It is
 * never trusted: the API authorizes every request against the signed-in account,
 * and the id is discarded when it is no longer in the account's child list.
 */
import { safeStorage } from '../utils/storage';

export const ACTIVE_CHILD_KEY = 'dyscover-active-child-id';
export const LAST_ASSESSMENT_KEY = 'dyscover-last-assessment-id';
const CHANGE_EVENT = 'dyscover-active-child-change';

// Keys that hold data tied to the signed-in account and must not survive logout.
const ACCOUNT_SCOPED_KEYS = [
  ACTIVE_CHILD_KEY,
  LAST_ASSESSMENT_KEY,
  'dyscover-stage2-child-id',
  'dyscover-stage2-assessment-id',
  'dyscover-assessment-event-queue',
  'dyscover-backend-trial-id-map',
  'dyscover-access-token',
  // Consent is given by the signed-in adult and must be asked again for the next one.
  'dyscover-gaze-consent',
  'dyscover-speech-consent',
];

export function getActiveChildId(): string | null {
  return safeStorage.getItem(ACTIVE_CHILD_KEY);
}

export function setActiveChildId(childId: string | null): void {
  if (childId) safeStorage.setItem(ACTIVE_CHILD_KEY, childId);
  else safeStorage.removeItem(ACTIVE_CHILD_KEY);
  safeStorage.removeItem(LAST_ASSESSMENT_KEY);
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function onActiveChildChange(listener: () => void): () => void {
  if (typeof window === 'undefined') return () => undefined;
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}

export function getLastAssessmentId(): string | null {
  return safeStorage.getItem(LAST_ASSESSMENT_KEY);
}

export function setLastAssessmentId(assessmentId: string): void {
  safeStorage.setItem(LAST_ASSESSMENT_KEY, assessmentId);
}

export function clearAccountScopedStorage(): void {
  for (const key of ACCOUNT_SCOPED_KEYS) safeStorage.removeItem(key);
}
