import { api, request, type SpeechSessionCreatePayload } from '../services/apiClient';
import type { GazeBatchPayload } from '../services/apiClient';
import { CONTENT_VERSION, getStoredLanguage, getStoredLocale } from '../l10n/languages';
import { enqueue, flushQueue, readTrialIdMap, updateTrialIdMap, type PersistedItem } from './engine';
import type { AssessmentEvent, AssessmentSession, GameResult, Trial } from './engine';
import type { SpeechTrial } from './speech/speechDefinitions';

const childKey = 'dyscover-stage2-child-id';
const assessmentKey = 'dyscover-stage2-assessment-id';

function sanitizeJsonValue(value: unknown): unknown {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (Array.isArray(value)) return value.map(sanitizeJsonValue);
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) out[key] = sanitizeJsonValue(item);
    return out;
  }
  return value;
}

function telemetryWarning(kind: string, path: string, error: unknown): void {
  if (import.meta.env.DEV) console.warn(`[Dyscover telemetry] ${kind} not persisted to ${path}:`, error);
}

export async function ensureAssessmentSession(): Promise<AssessmentSession> {
  void flushAssessmentQueue();
  let childId = localStorage.getItem(childKey);
  if (!childId) {
    const child = await api.createChild({ display_name: 'Explorer' });
    childId = child.id;
    localStorage.setItem(childKey, childId);
  }
  const assessment = await api.createAssessment({ child_id: childId, version: 'stage-2.0', language: getStoredLanguage(), locale: getStoredLocale(), content_version: CONTENT_VERSION });
  localStorage.setItem(assessmentKey, assessment.id);
  return {
    sessionId: assessment.id,
    assessmentId: assessment.id,
    childId,
    assessmentVersion: assessment.version,
    startedAt: new Date().toISOString(),
    status: 'NOT_STARTED',
    games: [],
    currentGameIndex: 0,
    totalTrials: 0,
  };
}

export async function persistTrial(assessmentId: string, gameId: string, trial: Trial): Promise<string | null> {
  const payload = {
    trial_number: trial.trialIndex + 1,
    stimulus: sanitizeJsonValue(trial.stimulus),
    expected_response: sanitizeJsonValue(trial.expectedResponse),
    actual_response: sanitizeJsonValue(trial.actualResponse),
    game_version: trial.gameVersion,
    domain: trial.domain,
    difficulty: trial.difficulty,
    score: Number.isFinite(trial.score) ? trial.score : 0,
    attempt_count: trial.attemptCount,
    error_count: trial.errorCount,
    metadata: sanitizeJsonValue(trial.metadata) ?? {},
    correctness: trial.correct,
    reaction_time_ms: Number.isFinite(trial.reactionTimeMs ?? NaN) ? trial.reactionTimeMs : null,
    hesitation_time_ms: Number.isFinite(trial.hesitationTimeMs ?? NaN) ? trial.hesitationTimeMs : null,
    started_at: trial.startedAt,
    completed_at: trial.completedAt,
  };
  const item: PersistedItem = { kind: 'trial', trialRef: trial.trialId, path: `/assessments/${assessmentId}/games/${gameId}/trials`, payload: payload as unknown as Trial };
  try {
    const remote = await api.createTrial(assessmentId, gameId, payload);
    updateTrialIdMap(trial.trialId, remote.id);
    return remote.id;
  } catch (error) {
    telemetryWarning('trial', item.path, error);
    enqueue(item);
    return null;
  }
}

export async function persistEvent(trialId: string, event: AssessmentEvent): Promise<void> {
  const payload = {
    event_type: event.eventType,
    session_id: event.sessionId,
    game_id: event.gameId,
    timestamp: event.timestamp,
    performance_time: Number.isFinite(event.performanceTime) ? event.performanceTime : null,
    sequence_number: event.sequenceNumber,
    schema_version: event.schemaVersion,
    payload: sanitizeJsonValue(event.payload) ?? {},
  };
  const item: PersistedItem = { kind: 'event', trialRef: event.trialId ?? trialId, path: `/trials/${trialId}/events`, payload: payload as unknown as AssessmentEvent };
  try {
    await api.createEvent(trialId, payload);
    updateTrialIdMap(event.trialId ?? trialId, trialId);
  } catch (error) {
    telemetryWarning('event', item.path, error);
    enqueue(item);
  }
}

export async function persistSummary(assessmentId: string, summary: { games: GameResult[]; totalTrials: number }): Promise<void> {
  try {
    await api.createSummary(assessmentId, summary);
  } catch (error) {
    telemetryWarning('summary', `/assessments/${assessmentId}/summary`, error);
    enqueue({ kind: 'event', path: `/assessments/${assessmentId}/summary`, payload: summary as unknown as AssessmentEvent });
  }
}

export async function persistGazeBatch(trialRef: string, backendTrialId: string | null, batch: GazeBatchPayload): Promise<void> {
  const item: PersistedItem = {
    kind: 'gaze',
    trialRef,
    path: '',
    payload: batch as unknown as Record<string, unknown>,
  };
  if (backendTrialId) {
    const path = `/gaze/trials/${backendTrialId}/gaze`;
    try {
      await captureApiPostGazeBatch(item, backendTrialId);
      return;
    } catch (error) {
      telemetryWarning('gaze', path, error);
      item.path = path;
      enqueue(item);
      return;
    }
  }
  enqueue(item);
}

export async function persistSpeechFeatures(sessionId: string, features: Record<string, unknown>): Promise<void> {
  try {
    await api.storeSpeechFeatures(sessionId, features);
  } catch (error) {
    telemetryWarning('speech', `/speech/sessions/${sessionId}/features`, error);
    enqueue({ kind: 'speech_features', path: `/speech/sessions/${sessionId}/features`, payload: { features } });
  }
}

export async function persistSpeechAssessmentTrial(assessmentId: string, trial: SpeechTrial, backendTrialId: string | null): Promise<void> {
  const evidence = trial.metadata.evidence;
  const features = trial.metadata.features;
  if (!evidence || !features) return;
  const taskId = trial.stimulus.taskId;
  const language = getStoredLanguage();
  const recordPayload = {
    session_id: assessmentId,
    trial_id: backendTrialId,
    task: {
      task_id: taskId,
      expected_text: trial.expectedResponse as string,
      language,
      difficulty: trial.difficulty,
      content_type: contentTypeFor(evidence.kind),
      version: trial.gameVersion,
    },
    language,
    provider: 'webkit-speech-v1',
    provider_version: '1.0',
    audio_available: false,
    duration_ms: Number.isFinite(evidence.durationMs) ? evidence.durationMs : null,
  };
  const item: PersistedItem = {
    kind: 'speech_session',
    trialRef: trial.trialId,
    path: '/speech/sessions',
    payload: { ...recordPayload, features },
  };
  if (!backendTrialId) {
    enqueue(item);
    return;
  }
  try {
    const created = await api.createSpeechSession(recordPayload);
    await api.storeSpeechFeatures(created.id, featureRecordPayload(features));
  } catch (error) {
    telemetryWarning('speech', item.path, error);
    enqueue(item);
  }
}

function contentTypeFor(kind: string): SpeechSessionCreatePayload['task']['content_type'] {
  switch (kind) {
    case 'letter':
    case 'letter-pair':
      return 'letter';
    case 'sentence':
      return 'sentence';
    case 'ran':
      return 'word';
    default:
      return 'word';
  }
}

function featureRecordPayload(features: Record<string, number>): Record<string, { value: number; available: boolean }> {
  const records: Record<string, { value: number; available: boolean }> = {};
  for (const [name, value] of Object.entries(features)) {
    if (typeof value === 'number' && Number.isFinite(value)) records[name] = { value, available: true };
  }
  return records;
}

async function captureApiPostGazeBatch(item: PersistedItem, backendTrialId: string): Promise<void> {
  const batch = item.payload as unknown as GazeBatchPayload;
  await api.postGazeBatch(backendTrialId, batch);
}

async function persistQueuedSpeechSession(item: PersistedItem, payload: Record<string, unknown>): Promise<void> {
  const backendTrialId = item.trialRef ? readTrialIdMap()[item.trialRef] : undefined;
  if (!backendTrialId && !payload.trial_id) throw new Error('Queued speech observations have no resolvable trial identifier');
  const body = { ...payload, trial_id: backendTrialId ?? payload.trial_id };
  const created = (await request(item.path, { method: 'POST', body: JSON.stringify(body) })) as { id?: string };
  if (created?.id && payload.features && typeof payload.features === 'object') {
    await request(`/speech/sessions/${created.id}/features`, { method: 'POST', body: JSON.stringify({ features: featureRecordPayload(payload.features as Record<string, number>) }) });
  }
}

export async function flushAssessmentQueue(): Promise<void> {
  await flushQueue(async item => {
    if (item.kind === 'trial') {
      const remote = (await request(item.path, { method: 'POST', body: JSON.stringify(item.payload) })) as { id?: string };
      if (remote?.id) updateTrialIdMap(item.trialRef, remote.id);
      return;
    }
    if (item.kind === 'gaze') {
      const backendId = item.trialRef ? readTrialIdMap()[item.trialRef] : undefined;
      if (!backendId) throw new Error('Queued gaze data has no resolvable trial identifier');
      await request(`/gaze/trials/${backendId}/gaze`, { method: 'POST', body: JSON.stringify(item.payload) });
      return;
    }
    if (item.kind === 'speech_features') {
      await request(item.path, { method: 'POST', body: JSON.stringify(item.payload) });
      return;
    }
    if (item.kind === 'speech_session') {
      const payload = item.payload as Record<string, unknown>;
      await persistQueuedSpeechSession(item, payload);
      return;
    }
    const backendId = item.trialRef ? readTrialIdMap()[item.trialRef] ?? item.trialRef : undefined;
    if (!backendId) throw new Error('Queued event has no resolvable trial identifier');
    await request(`/trials/${backendId}/events`, { method: 'POST', body: JSON.stringify(item.payload) });
  });
}