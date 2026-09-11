const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new ApiError(response.status, body.detail ?? 'The request could not be completed.'); }
  return response.json() as Promise<T>;
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
};
