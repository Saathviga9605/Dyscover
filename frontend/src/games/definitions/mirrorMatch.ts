import type { GameDefinition } from '../engine';
import { makeTrial } from './shared';

export type MirrorOrientation = 'normal' | 'mirror' | 'rotated';

export interface MirrorTrial {
	trialId: string;
	sessionId: string;
	gameId: string;
	gameVersion: string;
	trialIndex: number;
	domain: 'visual-symbol-discrimination';
	difficulty: number;
	startedAt: string;
	stimulus: {
		symbol: string;
		targetOrientation: MirrorOrientation;
		options: Array<{ id: string; label: string; orientation: MirrorOrientation }>;
	};
	expectedResponse: string;
	score: number;
	attemptCount: number;
	errorCount: number;
	metadata: Record<string, unknown>;
	correct?: boolean;
	completedAt?: string;
	responseAt?: string;
	reactionTimeMs?: number;
	actualResponse?: unknown;
}

const symbols = ['b', 'd', 'p', 'q', 'm', 'w'];
const ORIENTATIONS: MirrorOrientation[] = ['normal', 'mirror', 'rotated'];

export function orientationTransform(orientation: MirrorOrientation): string | undefined {
	return orientation === 'mirror' ? 'scaleX(-1)' : orientation === 'rotated' ? 'rotate(180deg)' : undefined;
}

export const mirrorMatch: GameDefinition<MirrorTrial> = {
	id: 'mirror-match',
	name: 'Mirror Match',
	description: 'Find the symbol that is facing the same way.',
	domain: 'visual-symbol-discrimination',
	gameVersion: '1.0.0',
	ageRange: [4, 10],
	estimatedDurationMinutes: 4,
	difficultyLevels: [1, 2, 3, 4, 5],
	instructions: ['Look at the example.', 'Find its matching direction.', 'A close look is a good look.'],
	totalTrials: 5,
	createTrial: ({ index, difficulty, random, sessionId }) => {
		const symbol = random.pick(symbols.slice(0, Math.min(symbols.length, 2 + difficulty)));
		const targetOrientation: MirrorOrientation = difficulty < 3 ? 'normal' : random.pick([...ORIENTATIONS]);
		const options = random.shuffle(ORIENTATIONS.map((orientation, position) => ({ id: `option-${position}`, label: symbol, orientation })));
		const correct = options.find(option => option.orientation === targetOrientation) ?? options[0];
		return makeTrial(index, sessionId, 'mirror-match', 'visual-symbol-discrimination', difficulty, { symbol, targetOrientation, options }, correct.id, { orientation: targetOrientation }) as MirrorTrial;
	},
	evaluateResponse: (trial, response) => {
		const chosen = trial.stimulus.options.find(option => option.id === response);
		const correct = chosen !== undefined && chosen.orientation === trial.stimulus.targetOrientation;
		return {
			correct,
			score: correct ? 1 : 0,
			actualResponse: response,
			metadata: {
				errorType: chosen ? (correct ? undefined : chosen.orientation === 'rotated' ? 'rotation' : 'orientation') : 'unknown_option',
				chosenOrientation: chosen?.orientation ?? null,
			},
		};
	},
	getNextDifficulty: history => history.at(-1)?.difficulty ?? 1,
};