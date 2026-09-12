const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new ApiError(response.status, body.detail ?? 'The request could not be completed.'); }
  return response.json() as Promise<T>;
}

export interface Skill {
  domain: string;
  label: string;
  evidence_state: string;
  category: string;
  confidence: string;
  reason?: string | null;
  observations: string[];
  accuracy?: number | null;
  trial_count: number;
}

export interface PersonalizationProfile {
  child_id: string;
  engine_version: string;
  schema_version: string;
  config_summary: { engine_version: string; config: Record<string, unknown> };
  mode: string;
  skills: Skill[];
}

export interface DifficultyDecision {
  level: number;
  previous_level?: number | null;
  default: number;
  window_size: number;
  reason: string;
  changed: boolean;
}

export interface Recommendation {
  game_id: string | null;
  target_domain: string | null;
  target_domain_label?: string | null;
  priority: number;
  reason: string;
  category: string;
  suggested_difficulty?: number | null;
  kind: 'game_activity' | 'neutral';
}

export interface PersonalizationRecommendations {
  child_id: string;
  engine_version: string;
  mode: string;
  recommendations: Recommendation[];
}

export interface ProgressPoint {
  assessment_id: string;
  completed_at?: string | null;
  domains: Record<string, number>;
}

export interface DomainDelta {
  earliest_accuracy: number;
  latest_accuracy: number;
  delta: number;
}

export interface ProgressResponse {
  child_id: string;
  engine_version: string;
  mode: string;
  points: ProgressPoint[];
  comparison?: {
    earliest_assessment_id: string;
    latest_assessment_id: string;
    domains: Record<string, DomainDelta>;
  } | null;
  note?: string | null;
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),
  createChild: (payload: { display_name: string }) => request<{ id: string; display_name: string; created_at: string }>('/children', { method: 'POST', body: JSON.stringify(payload) }),
  createAssessment: (payload: { child_id: string; version: string; language?: string; locale?: string; content_version?: string }) => request<{ id: string; child_id: string; version: string; status: string; started_at?: string }>('/assessments', { method: 'POST', body: JSON.stringify(payload) }),
  createTrial: (assessmentId: string, gameId: string, trial: Record<string, unknown>) => request<{ id: string }>(`/assessments/${assessmentId}/games/${gameId}/trials`, { method: 'POST', body: JSON.stringify(trial) }),
  createEvent: (trialId: string, event: Record<string, unknown>) => request(`/trials/${trialId}/events`, { method: 'POST', body: JSON.stringify(event) }),
  createSummary: (assessmentId: string, summary: Record<string, unknown>) => request(`/assessments/${assessmentId}/summary`, { method: 'POST', body: JSON.stringify(summary) }),
  listAssessments: (childId: string) => request<Array<{ id: string; completed_at?: string; status: string }>>(`/children/${childId}/assessments`),
  getProfile: (sessionId: string) => request<{ session_id: string; mode: string; domains: Record<string, { status: string; accuracy?: number }>; observations: string[]; data_quality: Record<string, unknown>; model: { status: string; limitations: string[] }; limitations: string[] }>(`/ml/profile/session/${sessionId}`),

  getPersonalizationProfile: (childId: string) => request<PersonalizationProfile>(`/personalization/children/${childId}/profile`),
  getPersonalizationDifficulty: (childId: string, gameId: string) => request<DifficultyDecision>(`/personalization/children/${childId}/difficulty/${gameId}`),
  getPersonalizationRecommendations: (childId: string, language?: string) => request<PersonalizationRecommendations>(`/personalization/children/${childId}/recommendations${language ? `?language=${language}` : ''}`),
  getPersonalizationProgress: (childId: string) => request<ProgressResponse>(`/personalization/children/${childId}/progress`),

  listRemedialActivities: (childId?: string, language?: string) => request<PracticeActivity[]>(`/remedial/activities${[childId && `child_id=${childId}`, language && `language=${language}`].filter(Boolean).join('&') ? `?${[childId && `child_id=${childId}`, language && `language=${language}`].filter(Boolean).join('&')}` : ''}`),
  getNextPracticeActivity: (childId: string, language?: string, capabilitiesOverride?: string) => request<NextPracticeActivity>(`/remedial/children/${childId}/next-activity${[language && `language=${language}`, capabilitiesOverride && `capabilities=${capabilitiesOverride}`].filter(Boolean).join('&') ? `?${[language && `language=${language}`, capabilitiesOverride && `capabilities=${capabilitiesOverride}`].filter(Boolean).join('&')}` : ''}`),
  getSpeechTasks: (activityId: string, count = 5, seed = 0, language?: string) => request<SpeechTasksResponse>(`/remedial/activities/${activityId}/speech-tasks?count=${count}&seed=${seed}${language ? `&language=${language}` : ''}`),
  createPracticeSession: (payload: { child_id: string; activity_id: string; difficulty?: number | null; language?: string }) => request<PracticeSessionStatus>('/remedial/sessions', { method: 'POST', body: JSON.stringify(payload) }),
  startPracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/start`, { method: 'POST' }),
  recordPracticeEvent: (sessionId: string, event: { event_type: string; payload: Record<string, unknown> }) => request<Record<string, unknown>>(`/remedial/sessions/${sessionId}/events`, { method: 'POST', body: JSON.stringify(event) }),
  completePracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/complete`, { method: 'POST' }),
  abandonPracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/abandon`, { method: 'POST' }),
  getPracticeProgress: (childId: string) => request<PracticeProgress>(`/remedial/children/${childId}/practice/progress`),

  getGazeStatus: () => request<GazeStatusResponse>('/gaze/status'),
  postGazeBatch: (trialId: string, batch: GazeBatchPayload) => request<GazeBatchResponse>(`/gaze/trials/${trialId}/gaze`, { method: 'POST', body: JSON.stringify(batch) }),
  getGazeBatch: (trialId: string) => request<GazeBatchResponse>(`/gaze/trials/${trialId}/gaze`),
  storeSpeechFeatures: (sessionId: string, features: Record<string, unknown>) => request<Record<string, unknown>>(`/speech/sessions/${sessionId}/features`, { method: 'POST', body: JSON.stringify({ features }) }),
  getSpeechFeatures: (sessionId: string) => request<Record<string, unknown>>(`/speech/sessions/${sessionId}/features`),
  createSpeechSession: (payload: SpeechSessionCreatePayload) => request<{ id: string; session_id: string; trial_id?: string | null }>('/speech/sessions', { method: 'POST', body: JSON.stringify(payload) }),
  getModalitySummary: (assessmentId: string) => request<ModalitySummaryResponse>(`/assessments/${assessmentId}/modality-summary`),
};

export interface PracticeActivity {
  activity_id: string;
  display_name: string;
  description: string;
  target_domain: string;
  supporting_game: string;
  supported_difficulty_levels: number[];
  age_range: [number, number];
  estimated_duration_minutes: number;
  activity_type: string;
  required_capabilities: string[];
  version: string;
  enabled: boolean;
}

export interface NextPracticeActivity {
  child_id: string;
  kind: 'focused' | 'balanced' | 'no_activity';
  activity: PracticeActivity | null;
  target_domain: string | null;
  target_domain_label: string | null;
  difficulty_level: number | null;
  difficulty_previous_level?: number | null;
  reason: string;
  recommendation_version: string;
  content_version: string;
}

export interface SpeechTask {
  task_id: string;
  expected_text: string;
  language: string;
  difficulty: number;
  content_type: 'word' | 'letter' | 'phrase' | 'sentence' | 'other';
  version: string;
}

export interface SpeechTasksResponse {
  activity_id: string;
  content_version: string;
  tasks: SpeechTask[];
}

export interface SpeechSessionCreatePayload {
  session_id: string;
  trial_id?: string | null;
  task: SpeechTask;
  language: string;
  provider: string;
  provider_version: string;
  audio_available: boolean;
  duration_ms?: number | null;
}

export interface ModalitySummaryResponse {
  assessment_id: string;
  gaze: {
    recorded: boolean;
    calibration_completed: boolean;
    trial_count: number;
    sample_count: number;
    fixation_count: number;
    trial_coverage: number;
    aoi_coverage: number;
  };
  speech: {
    recorded: boolean;
    trial_count: number;
    trial_coverage: number;
    transcript_available: number;
    response_timing_available: number;
    asr_available: number;
  };
}

export interface PracticeSessionStatus {
  id: string;
  child_id: string;
  mode: string;
  activity_id: string;
  target_domain: string;
  difficulty: number;
  activity_version: string;
  content_version: string;
  config_version: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface PracticeActivityRecord {
  activity_id: string;
  activity_name: string;
  target_domain: string;
  attempts: number;
  completed: number;
  accuracy_observed?: number | null;
  first_accuracy_observed?: number | null;
  latest_accuracy_observed?: number | null;
  last_completed_at?: string | null;
}

export interface PracticeProgress {
  child_id: string;
  totals: { sessions_attempted: number; sessions_completed: number; activities_completed: number; activities_available: number };
  by_activity: PracticeActivityRecord[];
  recent_completed: Array<{ id: string; activity_id: string; activity_name: string; difficulty: number; completed_at: string }>;
  note: string;
}

export interface GazeStatusResponse {
  recording: boolean;
  total_samples: number;
  trialsWithSamples: number;
  schema_version: string;
}

export interface GazeBatchResponse {
  samples_created: number;
  samples_rejected: number;
  fixations_created: number;
  quality: string;
  message: string;
}

export interface GazeBatchPayload {
  provider: string;
  providerVersion: string;
  quality: string;
  schemaVersion: string;
  samples: Array<{
    x: number;
    y: number;
    timestamp_ms: number;
    confidence?: number;
    quality: string;
    viewport_width: number;
    viewport_height: number;
  }>;
  fixations: Array<{
    start_timestamp_ms: number;
    end_timestamp_ms: number;
    duration_ms: number;
    x: number;
    y: number;
    target_type?: string;
    target_id?: string;
  }>;
}
