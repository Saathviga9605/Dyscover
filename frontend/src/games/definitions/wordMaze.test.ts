import { describe, expect, it } from 'vitest';
import { wordMaze } from './wordMaze';
import { createSeededRandom } from '../engine/random';
import { GameEngine } from '../engine/engine';

const seeds = [1, 42, 1337, 2024, 54321, 999983];

function mazeFor(seed: number, difficulty: number, index: number) {
	return wordMaze.createTrial({ index, difficulty, random: createSeededRandom(seed), sessionId: 'maze-session' });
}

const WORD_POOLS: Record<number, string[]> = {
	1: ['cat', 'sun', 'dog', 'map', 'hat', 'bed'],
	2: ['dog', 'map', 'fish', 'moon', 'star', 'tree', 'bird', 'frog', 'rain', 'sun', 'cat'],
	3: ['moon', 'star', 'tree', 'bird', 'fish', 'rain', 'boat', 'cake', 'lake', 'snow'],
	4: ['plant', 'cloud', 'train', 'beach', 'rocket', 'pencil', 'castle', 'garden', 'island', 'river'],
	5: ['bright', 'friend', 'garden', 'stream', 'flower', 'castle', 'island', 'harbour', 'sunset', 'balloon'],
};

describe('word maze freshness and validity', () => {
	it('A: completing every target resolves the mission as correct', () => {
		for (const seed of seeds) {
			const trial = mazeFor(seed, 2, 0);
			const evaluation = wordMaze.evaluateResponse(trial, trial.stimulus.targets);
			expect(evaluation.correct).toBe(true);
			expect(evaluation.metadata?.foundCount).toBe(trial.stimulus.targets.length);
		}
	});

	it('B: no word target is reused by the next mission in the same session', () => {
		for (const seed of seeds) {
			for (const difficulty of [1, 2, 3, 4, 5]) {
				const firstTargets = new Set(mazeFor(seed, difficulty, 0).stimulus.targets);
				const secondTargets = new Set(mazeFor(seed, difficulty, 1).stimulus.targets);
				expect([...firstTargets].some(target => secondTargets.has(target))).toBe(false);
			}
		}
	});

	it('C: target words change between missions', () => {
		for (const seed of seeds) {
			const first = mazeFor(seed, 2, 0).stimulus.targets.join(',');
			const second = mazeFor(seed, 2, 1).stimulus.targets.join(',');
			const third = mazeFor(seed, 2, 2).stimulus.targets.join(',');
			expect(new Set([first, second, third]).size).toBe(3);
		}
	});

	it('D: target placement varies between missions', () => {
		for (const seed of seeds) {
			const firstStarts = Object.values(mazeFor(seed, 3, 0).stimulus.paths).map(path => path[0]).sort();
			const secondStarts = Object.values(mazeFor(seed, 3, 1).stimulus.paths).map(path => path[0]).sort();
			expect(firstStarts).not.toEqual(secondStarts);
		}
	});

	it('E: distractor letters differ between missions of the same session', () => {
		const background = (trial: ReturnType<typeof mazeFor>) => {
			const covered = new Set(Object.values(trial.stimulus.paths).flat());
			return trial.stimulus.grid.flatMap((row, r) => row.map((letter, c) => (covered.has(`${r},${c}`) ? '_' : letter))).join('');
		};
		for (const seed of seeds) {
			const first = background(mazeFor(seed, 2, 0));
			const second = background(mazeFor(seed, 2, 1));
			expect(first).not.toEqual(second);
		}
	});

	it('F: every generated maze is valid; words are placed inside the grid with their letters', () => {
		for (const seed of seeds) {
			for (const difficulty of [1, 2, 3, 4, 5]) {
				const trial = mazeFor(seed, difficulty, 0);
				const { size, grid, targets, paths } = trial.stimulus;
				expect(grid).toHaveLength(size);
				grid.forEach(row => expect(row).toHaveLength(size));
				expect(Object.keys(paths).sort()).toEqual([...new Set(targets)].sort());
				targets.forEach(target => {
					const path = paths[target];
					expect(path).toBeDefined();
					path.forEach((cell, offset) => {
						const [row, col] = cell.split(',').map(Number);
						expect(row).toBeGreaterThanOrEqual(0);
						expect(row).toBeLessThan(size);
						expect(col).toBeGreaterThanOrEqual(0);
						expect(col).toBeLessThan(size);
						expect(grid[row][col]).toBe(target[offset]);
					});
				});
			}
		}
	});

	it('G: difficulty controls target count and grid size', () => {
		expect(mazeFor(1, 1, 0).stimulus.targets).toHaveLength(2);
		expect(mazeFor(1, 1, 0).stimulus.size).toBe(6);
		expect(mazeFor(1, 2, 0).stimulus.targets).toHaveLength(3);
		expect(mazeFor(1, 2, 0).stimulus.size).toBe(6);
		expect(mazeFor(1, 3, 0).stimulus.size).toBe(8);
		expect(mazeFor(1, 4, 0).stimulus.size).toBe(8);
		expect(mazeFor(1, 5, 0).stimulus.size).toBe(8);
	});

	it('H: all target words come from the difficulty-appropriate real-word pool', () => {
		for (const seed of seeds) {
			for (const difficulty of [1, 2, 3, 4, 5]) {
				mazeFor(seed, difficulty, 0).stimulus.targets.forEach(target => {
					expect(WORD_POOLS[difficulty]).toContain(target.toLowerCase());
				});
			}
		}
	});

	it('I: engine telemetry records the completed word set and correctness', () => {
		const engine = new GameEngine(wordMaze, undefined, 1337);
		engine.start();
		const trial = engine.beginTrial();
		engine.recordResponse(trial, trial.stimulus.targets);
		expect(trial.correct).toBe(true);
		expect(trial.actualResponse).toEqual(trial.stimulus.targets);
		engine.completeTrial(trial);
		const submitted = engine.events.find(event => event.eventType === 'RESPONSE_SUBMITTED');
		expect(submitted?.payload.response).toEqual(trial.stimulus.targets);
		expect(submitted?.payload.correct).toBe(true);
	});

	it('J: session completion is unchanged after completing a maze mission', () => {
		const engine = new GameEngine(wordMaze, undefined, 2024);
		engine.start();
		const trial = engine.beginTrial();
		engine.recordResponse(trial, trial.stimulus.targets);
		engine.completeTrial(trial);
		engine.completeSession();
		expect(engine.session.status).toBe('COMPLETED');
		expect(engine.session.completedAt).toBeDefined();
	});
});