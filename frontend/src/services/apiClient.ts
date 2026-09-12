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
  createAssessment: (payload: { child_id: string; version: string }) => request<{ id: string; child_id: string; version: string; status: string; started_at?: string }>('/assessments', { method: 'POST', body: JSON.stringify(payload) }),
  createTrial: (assessmentId: string, gameId: string, trial: Record<string, unknown>) => request<{ id: string }>(`/assessments/${assessmentId}/games/${gameId}/trials`, { method: 'POST', body: JSON.stringify(trial) }),
  createEvent: (trialId: string, event: Record<string, unknown>) => request(`/trials/${trialId}/events`, { method: 'POST', body: JSON.stringify(event) }),
  createSummary: (assessmentId: string, summary: Record<string, unknown>) => request(`/assessments/${assessmentId}/summary`, { method: 'POST', body: JSON.stringify(summary) }),
  listAssessments: (childId: string) => request<Array<{ id: string; completed_at?: string; status: string }>>(`/children/${childId}/assessments`),
  getProfile: (sessionId: string) => request<{ session_id: string; mode: string; domains: Record<string, { status: string; accuracy?: number }>; observations: string[]; data_quality: Record<string, unknown>; model: { status: string; limitations: string[] }; limitations: string[] }>(`/ml/profile/session/${sessionId}`),

  getPersonalizationProfile: (childId: string) => request<PersonalizationProfile>(`/personalization/children/${childId}/profile`),
  getPersonalizationDifficulty: (childId: string, gameId: string) => request<DifficultyDecision>(`/personalization/children/${childId}/difficulty/${gameId}`),
  getPersonalizationRecommendations: (childId: string) => request<PersonalizationRecommendations>(`/personalization/children/${childId}/recommendations`),
  getPersonalizationProgress: (childId: string) => request<ProgressResponse>(`/personalization/children/${childId}/progress`),

  listRemedialActivities: (childId?: string) => request<PracticeActivity[]>(`/remedial/activities${childId ? `?child_id=${childId}` : ''}`),
  getNextPracticeActivity: (childId: string) => request<NextPracticeActivity>(`/remedial/children/${childId}/next-activity`),
  createPracticeSession: (payload: { child_id: string; activity_id: string; difficulty?: number | null }) => request<PracticeSessionStatus>('/remedial/sessions', { method: 'POST', body: JSON.stringify(payload) }),
  startPracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/start`, { method: 'POST' }),
  recordPracticeEvent: (sessionId: string, event: { event_type: string; payload: Record<string, unknown> }) => request<Record<string, unknown>>(`/remedial/sessions/${sessionId}/events`, { method: 'POST', body: JSON.stringify(event) }),
  completePracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/complete`, { method: 'POST' }),
  abandonPracticeSession: (sessionId: string) => request<PracticeSessionStatus>(`/remedial/sessions/${sessionId}/abandon`, { method: 'POST' }),
  getPracticeProgress: (childId: string) => request<PracticeProgress>(`/remedial/children/${childId}/practice/progress`),
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
