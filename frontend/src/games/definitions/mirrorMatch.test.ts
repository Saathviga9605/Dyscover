import { describe, expect, it } from 'vitest';
import { mirrorMatch, orientationTransform } from './mirrorMatch';
import { createSeededRandom } from '../engine/random';
import { GameEngine } from '../engine/engine';

const seeds = [1, 42, 1337, 2024, 54321, 999983, 7, 88, 31337, 123456789];

function trialFor(seed: number, difficulty: number) {
	return mirrorMatch.createTrial({ index: 0, difficulty, random: createSeededRandom(seed), sessionId: 'mirror-test' });
}

describe('mirror match reliability', () => {
	it('A: offers three distinct options without duplicate orientations', () => {
		const trial = trialFor(1, 5);
		expect(trial.stimulus.options).toHaveLength(3);
		expect(new Set(trial.stimulus.options.map(option => option.id)).size).toBe(3);
		expect(new Set(trial.stimulus.options.map(option => option.orientation)).size).toBe(3);
		expect(trial.stimulus.options.map(option => option.orientation).sort()).toEqual(['mirror', 'normal', 'rotated']);
		expect(new Set(trial.stimulus.options.map(option => option.label)).size).toBe(1);
	});

	it('B: correct option always matches the target orientation across seeds', () => {
		for (const seed of seeds) {
			const trial = trialFor(seed, 5);
			const correctOption = trial.stimulus.options.find(option => option.id === trial.expectedResponse);
			expect(correctOption).toBeDefined();
			expect(correctOption!.orientation).toBe(trial.stimulus.targetOrientation);
			expect(correctOption!.label).toBe(trial.stimulus.symbol);
			const evaluation = mirrorMatch.evaluateResponse(trial, trial.expectedResponse);
			expect(evaluation.correct).toBe(true);
			expect(evaluation.metadata?.chosenOrientation).toBe(trial.stimulus.targetOrientation);
		}
	});

	it('C: evaluation accepts only the option with the matching orientation', () => {
		for (const seed of seeds) {
			const trial = trialFor(seed, 5);
			for (const option of trial.stimulus.options) {
				const evaluation = mirrorMatch.evaluateResponse(trial, option.id);
				expect(evaluation.correct).toBe(option.orientation === trial.stimulus.targetOrientation);
			}
		}
	});

	it('D: correct option is not always first and its position varies', () => {
		const positions = seeds.map(seed => trialFor(seed, 5).stimulus.options.findIndex(option => option.id === trialFor(seed, 5).expectedResponse));
		expect(new Set(positions).size).toBeGreaterThan(1);
		expect(positions.some(position => position !== 0)).toBe(true);
	});

	it('E: every option position can be the correct one across seeds', () => {
		const positions = new Set<number>();
		for (let seed = 1; seed <= 120; seed += 1) {
			const trial = trialFor(seed, 5);
			positions.add(trial.stimulus.options.findIndex(option => option.id === trial.expectedResponse));
		}
		expect(positions.has(0)).toBe(true);
		expect(positions.has(1)).toBe(true);
		expect(positions.has(2)).toBe(true);
	});

	it('F: a mirrored representation is present in state and rendered as a real flip', () => {
		for (const seed of seeds) {
			const trial = trialFor(seed, 5);
			expect(trial.stimulus.options.some(option => option.orientation === 'mirror')).toBe(true);
			expect(trial.stimulus.options.some(option => option.orientation === 'rotated')).toBe(true);
		}
		expect(orientationTransform('mirror')).toBe('scaleX(-1)');
		expect(orientationTransform('rotated')).toBe('rotate(180deg)');
		expect(orientationTransform('normal')).toBeUndefined();
	});

	it('G: every difficulty level produces a valid trial', () => {
		for (let difficulty = 1; difficulty <= 5; difficulty += 1) {
			const trial = trialFor(7, difficulty);
			expect(trial.difficulty).toBe(difficulty);
			expect(trial.stimulus.options).toHaveLength(3);
			expect(trial.stimulus.symbol).toBeTruthy();
		}
	});

	it('H: low difficulty stays with a normal target; higher difficulty can present mirror or rotated targets', () => {
		expect(trialFor(7, 1).stimulus.targetOrientation).toBe('normal');
		expect(trialFor(7, 2).stimulus.targetOrientation).toBe('normal');
		const varied = seeds.some(seed => ['mirror', 'rotated'].includes(trialFor(seed, 5).stimulus.targetOrientation));
		expect(varied).toBe(true);
	});

	it('I: engine telemetry records the selected option and correctness', () => {
		const engine = new GameEngine(mirrorMatch, undefined, 4242);
		engine.start();
		const trial = engine.beginTrial();
		const wrongTarget = trial.stimulus.options.find(option => option.orientation !== trial.stimulus.targetOrientation);
		expect(wrongTarget).toBeDefined();
		engine.recordResponse(trial, wrongTarget!.id);
		expect(trial.correct).toBe(false);
		expect(trial.actualResponse).toBe(wrongTarget!.id);
		engine.completeTrial(trial);
		const submitted = engine.events.find(event => event.eventType === 'RESPONSE_SUBMITTED');
		expect(submitted?.payload.response).toBe(wrongTarget!.id);
		expect(submitted?.payload.correct).toBe(false);

		const engine2 = new GameEngine(mirrorMatch, undefined, 4242);
		engine2.start();
		const goodTrial = engine2.beginTrial();
		engine2.recordResponse(goodTrial, goodTrial.expectedResponse);
		expect(goodTrial.correct).toBe(true);
		expect(engine2.events.find(event => event.eventType === 'RESPONSE_SUBMITTED')?.payload.correct).toBe(true);
	});
});