/**
 * Dyscover API client.
 *
 * - Same-origin by default (`/api`): Vite proxies it in development and nginx in
 *   production, so the refresh cookie is first-party. `VITE_API_URL` overrides.
 * - The access token lives in memory only (never localStorage). On a 401 the
 *   client performs one shared refresh using the HttpOnly cookie and retries once.
 */
const baseUrl: string = ((import.meta.env.VITE_API_URL as string | undefined) ?? '/api').replace(
  /\/$/,
  ''
);

export const CSRF_HEADER = { 'X-Requested-With': 'dyscover' } as const;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly data: unknown,
    public readonly code?: string
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let sessionExpiredHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Called when the session cannot be refreshed (e.g. to reset auth state). */
export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

function errorMessage(body: unknown): { message: string; code?: string } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return { message: detail };
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const { message, code } = detail as { message?: unknown; code?: unknown };
    if (typeof message === 'string')
      return { message, code: typeof code === 'string' ? code : undefined };
  }
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: unknown; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? String(first.loc.at(-1) ?? '') : '';
    if (typeof first.msg === 'string')
      return { message: field ? `${field}: ${first.msg}` : first.msg, code: 'validation' };
  }
  return { message: 'The request could not be completed.' };
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const type = response.headers.get('content-type') ?? '';
  if (type.includes('application/json')) return response.json().catch(() => undefined);
  return undefined;
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${baseUrl}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...CSRF_HEADER },
    })
      .then(async response => {
        if (!response.ok) {
          setAccessToken(null);
          return false;
        }
        const body = (await response.json()) as TokenResponse;
        setAccessToken(body.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

async function send(path: string, init: RequestInit, retried = false): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken && !headers.has('Authorization'))
    headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers, credentials: 'include' });
  if (
    response.status === 401 &&
    !retried &&
    !NO_REFRESH_PATHS.some(prefix => path.startsWith(prefix))
  ) {
    if (await refreshSession()) return send(path, init, true);
    sessionExpiredHandler?.();
  }
  return response;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    options.body !== undefined &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await send(path, { ...options, headers });
  } catch (error) {
    throw new ApiError(
      0,
      'Could not reach Dyscover. Check your connection and try again.',
      error,
      'network'
    );
  }
  const body = await parseBody(response);
  if (!response.ok) {
    const { message, code } = errorMessage(body);
    throw new ApiError(response.status, message, body, code);
  }
  return body as T;
}

export async function requestBlob(path: string): Promise<Blob> {
  const response = await send(path, { method: 'GET' });
  if (!response.ok) {
    const { message, code } = errorMessage(await parseBody(response));
    throw new ApiError(response.status, message, undefined, code);
  }
  return response.blob();
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export async function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' });
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, json('POST', body));
}

export async function postForm<T>(path: string, formData: FormData): Promise<T> {
  return request<T>(path, { method: 'POST', body: formData });
}

export async function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, json('PATCH', body));
}

export async function del<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, json('DELETE', body));
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
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

export interface EducatorObservationDomain {
  domain: string;
  evidence_trials: number;
  accuracy?: number | null;
  quality?: string | null;
}

export interface EducatorLearnerSummary {
  child_id: string;
  display_name: string;
  completed_assessment_count: number;
  language_context: string[];
  observation_summary: string;
  domains: EducatorObservationDomain[];
  practice_summary: {
    completed_sessions: number;
    activity_count: number;
    activities: string[];
  };
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),

  // Children (owner-scoped)
  listChildren: () => request<ChildProfile[]>('/children'),
  createChild: (payload: { display_name: string; birth_year?: number }) =>
    request<ChildProfile>('/children', json('POST', payload)),
  updateChild: (childId: string, payload: { display_name?: string; birth_year?: number | null }) =>
    request<ChildProfile>(`/children/${childId}`, json('PATCH', payload)),
  deleteChild: (childId: string) => request<void>(`/children/${childId}`, json('DELETE')),
  listEducatorGrants: (childId: string) =>
    request<EducatorGrant[]>(`/children/${childId}/educators`),
  grantEducator: (childId: string, educatorEmail: string) =>
    request<EducatorGrant>(
      `/children/${childId}/educators`,
      json('POST', { educator_email: educatorEmail })
    ),
  revokeEducator: (childId: string, educatorId: string) =>
    request<void>(`/children/${childId}/educators/${educatorId}`, json('DELETE')),

  // Assessments
  createAssessment: (payload: {
    child_id: string;
    version: string;
    language?: string;
    locale?: string;
    content_version?: string;
  }) => request<AssessmentRecord>('/assessments', json('POST', payload)),
  createTrial: (assessmentId: string, gameId: string, trial: Record<string, unknown>) =>
    request<{ id: string }>(
      `/assessments/${assessmentId}/games/${gameId}/trials`,
      json('POST', trial)
    ),
  createEvent: (trialId: string, event: Record<string, unknown>) =>
    request(`/trials/${trialId}/events`, json('POST', event)),
  createSummary: (assessmentId: string, summary: Record<string, unknown>) =>
    request(`/assessments/${assessmentId}/summary`, json('POST', summary)),
  listAssessments: (childId: string, limit = 50) =>
    request<AssessmentRecord[]>(`/children/${childId}/assessments${query({ limit })}`),
  getProfile: (sessionId: string) =>
    request<{
      session_id: string;
      mode: string;
      domains: Record<string, { status: string; accuracy?: number }>;
      observations: string[];
      data_quality: Record<string, unknown>;
      model: { status: string; limitations: string[] };
      limitations: string[];
    }>(`/ml/profile/session/${sessionId}`),

  // Reading-difficulty screening (latest completed assessment)
  getScreening: (childId: string) => request<ScreeningResponse>(`/screening/children/${childId}`),

  // Synthetic research predictor (404 unless the server enables research mode)
  getResearchOverview: (childId: string) =>
    request<ResearchOverview>(`/screening/research/children/${childId}`),
  runResearchPrediction: (childId: string, assessmentId: string) =>
    request<ResearchPredictionResponse>(
      `/screening/research/children/${childId}/assessments/${assessmentId}/predict`,
      json('POST')
    ),

  // Educator workspace (role checked server-side)
  getEducatorLearners: () => request<EducatorLearnerSummary[]>('/educator/learners'),
  getEducatorLearnerSummary: (childId: string) =>
    request<EducatorLearnerSummary>(`/educator/learners/${childId}/summary`),
  leaveEducatorLearner: (childId: string) =>
    request<void>(`/educator/learners/${childId}/revoke`, json('POST')),

  getPersonalizationProfile: (childId: string) =>
    request<PersonalizationProfile>(`/personalization/children/${childId}/profile`),
  getPersonalizationDifficulty: (childId: string, gameId: string) =>
    request<DifficultyDecision>(`/personalization/children/${childId}/difficulty/${gameId}`),
  getPersonalizationRecommendations: (childId: string, language?: string) =>
    request<PersonalizationRecommendations>(
      `/personalization/children/${childId}/recommendations${query({ language })}`
    ),
  getPersonalizationProgress: (childId: string) =>
    request<ProgressResponse>(`/personalization/children/${childId}/progress`),

  listRemedialActivities: (childId?: string, language?: string) =>
    request<PracticeActivity[]>(`/remedial/activities${query({ child_id: childId, language })}`),
  getNextPracticeActivity: (childId: string, language?: string, capabilitiesOverride?: string) =>
    request<NextPracticeActivity>(
      `/remedial/children/${childId}/next-activity${query({ language, capabilities: capabilitiesOverride })}`
    ),
  getSpeechTasks: (activityId: string, count = 5, seed = 0, language?: string) =>
    request<SpeechTasksResponse>(
      `/remedial/activities/${activityId}/speech-tasks${query({ count, seed, language })}`
    ),
  createPracticeSession: (payload: {
    child_id: string;
    activity_id: string;
    difficulty?: number | null;
    language?: string;
  }) => request<PracticeSessionStatus>('/remedial/sessions', json('POST', payload)),
  startPracticeSession: (sessionId: string) =>
    request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/start`, json('POST')),
  recordPracticeEvent: (
    sessionId: string,
    event: { event_type: string; payload: Record<string, unknown> }
  ) =>
    request<Record<string, unknown>>(`/remedial/sessions/${sessionId}/events`, json('POST', event)),
  completePracticeSession: (sessionId: string) =>
    request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/complete`, json('POST')),
  abandonPracticeSession: (sessionId: string) =>
    request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/abandon`, json('POST')),
  getPracticeProgress: (childId: string) =>
    request<PracticeProgress>(`/remedial/children/${childId}/practice/progress`),

  getGazeStatus: () => request<GazeStatusResponse>('/gaze/status'),
  postGazeBatch: (trialId: string, batch: GazeBatchPayload) =>
    request<GazeBatchResponse>(`/gaze/trials/${trialId}/gaze`, json('POST', batch)),
  storeSpeechFeatures: (sessionId: string, features: Record<string, unknown>) =>
    request<Record<string, unknown>>(
      `/speech/sessions/${sessionId}/features`,
      json('POST', { features })
    ),
  getSpeechFeatures: (sessionId: string) =>
    request<Record<string, unknown>>(`/speech/sessions/${sessionId}/features`),
  createSpeechSession: (payload: SpeechSessionCreatePayload) =>
    request<{ id: string; session_id: string; trial_id?: string | null }>(
      '/speech/sessions',
      json('POST', payload)
    ),
  getModalitySummary: (assessmentId: string) =>
    request<ModalitySummaryResponse>(`/assessments/${assessmentId}/modality-summary`),

  // Speech demo (local providers only; audio is deleted after transcription)
  getSpeechDemoProviders: () =>
    request<{
      current_provider: string;
      current_provider_status: string;
      providers: Record<string, unknown>;
    }>('/speech/demo/providers'),
  transcribeSpeechDemo: (formData: FormData) =>
    postForm<{
      transcript: unknown;
      provider: string;
      provider_version: string;
      audio_info: unknown;
    }>('/speech/demo/transcribe', formData),
  compareSpeechDemo: (formData: FormData) =>
    postForm<{ audio_info: unknown; results: Record<string, unknown> }>(
      '/speech/demo/compare',
      formData
    ),
  getSpeechDemoModels: () =>
    request<{ huggingface_whisper: unknown; faster_whisper: unknown }>('/speech/demo/models'),

  // Auth
  register: (payload: UserRegister) =>
    request<UserResponse>('/auth/register', json('POST', payload)),
  login: (payload: UserLogin) => request<TokenResponse>('/auth/login', json('POST', payload)),
  logout: () => request<void>('/auth/logout', { method: 'POST', headers: { ...CSRF_HEADER } }),
  logoutEverywhere: () => request<void>('/auth/logout-all', json('POST')),
  getCurrentUser: () => request<CurrentUser>('/auth/me'),
  changePassword: (payload: { current_password: string; new_password: string }) =>
    request<TokenResponse>('/auth/change-password', json('POST', payload)),

  // Privacy
  getDataSummary: () => request<DataSummary>('/privacy/data-summary'),
  exportData: () => requestBlob('/privacy/export'),
  deleteAccount: (password: string) =>
    request<void>('/privacy/account', json('DELETE', { password })),

  // Lexi
  getChatStatus: () => request<ChatStatus>('/chat/status'),
  listConversations: () => request<Conversation[]>('/chat/conversations'),
  createConversation: () => request<Conversation>('/chat/conversations', json('POST', {})),
  deleteConversation: (conversationId: string) =>
    request<void>(`/chat/conversations/${conversationId}`, json('DELETE')),
  listMessages: (conversationId: string, before?: string) =>
    request<MessagePage>(
      `/chat/conversations/${conversationId}/messages${query({ before, limit: 50 })}`
    ),
  sendMessage: (conversationId: string, content: string, clientMessageId: string) =>
    request<ChatExchange>(
      `/chat/conversations/${conversationId}/messages`,
      json('POST', { content, client_message_id: clientMessageId })
    ),
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
    trial_coverage: number | null;
    aoi_coverage: number | null;
  };
  speech: {
    recorded: boolean;
    trial_count: number;
    trial_coverage: number | null;
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
  totals: {
    sessions_attempted: number;
    sessions_completed: number;
    activities_completed: number;
    activities_available: number;
  };
  by_activity: PracticeActivityRecord[];
  recent_completed: Array<{
    id: string;
    activity_id: string;
    activity_name: string;
    difficulty: number;
    completed_at: string;
  }>;
  note: string;
}

/** Mirrors backend app/gaze/schemas.py GazeStatusResponse. */
export interface GazeStatusResponse {
  modality: 'gaze';
  available: boolean;
  sample_schema_version: string;
  message: string;
  raw_media_stored: boolean;
}

/** Mirrors backend app/gaze/schemas.py GazeBatchResponse. */
export interface GazeBatchResponse {
  trial_id: string;
  samples_created: number;
  samples_rejected: number;
  fixations_created: number;
  fixations_rejected: number;
  quality: string;
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

// Auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export type UserRole = 'parent' | 'educator' | 'admin';

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface UserResponse extends CurrentUser {
  created_at: string;
}

export interface UserRegister {
  email: string;
  password: string;
  display_name: string;
  role?: 'parent' | 'educator';
}

export interface UserLogin {
  email: string;
  password: string;
}

// Children
export interface ChildProfile {
  id: string;
  display_name: string;
  birth_year?: number | null;
  created_at: string;
}

export interface EducatorGrant {
  child_id: string;
  educator_id: string;
  educator_display_name: string | null;
  status: string;
  created_at: string;
}

export interface AssessmentRecord {
  id: string;
  child_id: string;
  version: string;
  language: string;
  status: string;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

// Privacy
export interface DataSummary {
  user: { id: string; email: string; role: string; created_at: string | null };
  children: {
    count: number;
    details: Array<{ id: string; display_name: string; birth_year: number | null }>;
  };
  assessments: { count: number };
  trials: { count: number };
  interaction_events: { count: number };
  speech_sessions: { count: number };
  practice_sessions: { count: number };
  lexi_conversations: { count: number };
  retention: string;
}

// Lexi
export interface ChatStatus {
  configured: boolean;
  provider: string;
  model: string | null;
}

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface MessagePage {
  messages: ChatMessage[];
  has_more: boolean;
}

export interface ChatExchange {
  conversation: Conversation;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}

// Screening (mirrors backend app/ml/screening/service.py)
export type ScreeningStatus =
  | 'available'
  | 'no_assessment'
  | 'assessment_incomplete'
  | 'no_eligible_model'
  | 'unsupported_population'
  | 'insufficient_observations'
  | 'invalid_features';

export interface ScreeningResponse {
  child_id: string;
  assessment_id: string | null;
  assessment_completed_at: string | null;
  target_definition: string;
  feature_schema_version: string;
  status: ScreeningStatus;
  reasons: string[];
  models_considered: number;
  model: {
    model_id: string;
    model_version: string;
    model_name: string;
    output_type: 'calibrated_probability' | 'research_score';
    feature_schema_version: string;
  } | null;
  result: {
    score: number;
    score_percent: number;
    output_type: 'calibrated_probability' | 'research_score';
    band: string | null;
    created_at: string;
  } | null;
  observations: {
    scored_trials: number;
    unscored_trials: number;
    games_played: string[];
    domains: Array<{ domain: string; scored_trials: number; accuracy: number | null }>;
    strengths: string[];
    support_areas: string[];
    speech_recorded: boolean;
    gaze_recorded: boolean;
  };
}

export interface ResearchModelSummary {
  model_id: string;
  model_version: string;
  model_name: string;
  algorithm: string;
  designation: 'synthetic_research';
  training_data: 'synthetic';
  output_type: 'calibrated_probability' | 'research_score';
  target_id: string;
  target_definition: string;
  feature_schema_version: string;
  artifact_sha256: string;
  created_at: string;
  synthetic_test_metrics: Record<
    'roc_auc' | 'pr_auc' | 'brier' | 'sensitivity' | 'specificity',
    number | null
  >;
  synthetic_test_counts: { rows: number; participants: number } | null;
  inputs: { min_scored_trials: number; languages: string[]; age_min: number; age_max: number };
}

export interface ResearchOverview {
  label: string;
  notice: string;
  child_id: string;
  model: ResearchModelSummary | null;
  model_problems: string[];
  assessments: Array<{
    assessment_id: string;
    status: string;
    language: string;
    created_at: string | null;
    completed_at: string | null;
    has_prediction: boolean;
  }>;
}

export type ResearchStatus =
  | 'available'
  | 'no_research_model'
  | 'assessment_incomplete'
  | 'unsupported_population'
  | 'insufficient_observations'
  | 'invalid_features'
  | 'model_version_conflict';

export interface ResearchFeature {
  name: string;
  modality: string;
  value: number | null;
  available: boolean;
  training_median: number | null;
  outside_training_range: boolean | null;
  score_change_if_typical: number | null;
}

export interface ResearchPredictionResponse {
  label: string;
  notice: string;
  child_id: string;
  assessment_id: string;
  status: ResearchStatus;
  reasons: string[];
  notes: string[];
  model: ResearchModelSummary | null;
  observations: {
    scored_trials: number;
    unscored_trials: number;
    games_played: string[];
    speech_recorded: boolean;
    gaze_recorded: boolean;
  };
  features: ResearchFeature[];
  result: {
    score: number;
    score_percent: number;
    output_type: 'calibrated_probability' | 'research_score';
    created_at: string;
  } | null;
}
