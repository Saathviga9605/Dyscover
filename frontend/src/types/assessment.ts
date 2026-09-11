export const assessmentDomains = ['visual-symbol-discrimination', 'orthographic-recognition', 'phonological-awareness', 'working-memory', 'sequencing', 'attention-visual-search', 'reading-fluency', 'interaction-behavior'] as const;
export type AssessmentDomain = typeof assessmentDomains[number];

export type AssessmentEventType = 'trial_started' | 'stimulus_presented' | 'click' | 'selection' | 'response' | 'correct_response' | 'incorrect_response' | 'trial_completed' | 'gaze_sample' | 'fixation_started' | 'fixation_ended';

export interface TrialRecord { id: string; trialNumber: number; stimulus: string; expectedResponse?: string; actualResponse?: string; correctness?: boolean; reactionTimeMs?: number; hesitationTimeMs?: number; }
export interface InteractionEvent { type: AssessmentEventType; timestamp: string; payload: Record<string, unknown>; }
