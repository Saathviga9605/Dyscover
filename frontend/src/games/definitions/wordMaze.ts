import type { GameDefinition } from '../engine';
import { makeTrial } from './shared';

export interface MazeTrial {
	trialId: string;
	sessionId: string;
	gameId: string;
	gameVersion: string;
	trialIndex: number;
	domain: 'attention-visual-search';
	difficulty: number;
	startedAt: string;
	stimulus: { size: number; grid: string[][]; targets: string[]; paths: Record<string, string[]> };
	expectedResponse: string[];
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

const WORD_POOLS: Record<number, string[]> = {
	1: ['cat', 'sun', 'dog', 'map', 'hat', 'bed'],
	2: ['dog', 'map', 'fish', 'moon', 'star', 'tree', 'bird', 'frog', 'rain', 'sun', 'cat'],
	3: ['moon', 'star', 'tree', 'bird', 'fish', 'rain', 'boat', 'cake', 'lake', 'snow'],
	4: ['plant', 'cloud', 'train', 'beach', 'rocket', 'pencil', 'castle', 'garden', 'island', 'river'],
	5: ['bright', 'friend', 'garden', 'stream', 'flower', 'castle', 'island', 'harbour', 'sunset', 'balloon'],
};

const UPPER_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

function targetCount(difficulty: number): number {
	return difficulty === 1 ? 2 : 3;
}

function selectWords(index: number, difficulty: number, sessionId: string): string[] {
	const pool = WORD_POOLS[difficulty] ?? WORD_POOLS[1];
	const count = targetCount(difficulty);
	const sessionOffset = [...sessionId].reduce((sum, char) => (sum + char.charCodeAt(0)) % 97, 0);
	const offset = (index * count + sessionOffset) % pool.length;
	const words: string[] = [];
	for (let i = 0; i < count; i += 1) {
		words.push(pool[(offset + i) % pool.length]);
	}
	return words;
}

interface PlacementRandom {
	pick: <T>(items: T[]) => T;
	int: (min: number, max: number) => number;
	shuffle: <T>(items: T[]) => T[];
}

function parseCell(cell: string): { row: number; col: number } {
	const [row, col] = cell.split(',').map(Number);
	return { row, col };
}

function buildMaze(difficulty: number, index: number, sessionId: string, random: PlacementRandom): { size: number; grid: string[][]; targets: string[]; paths: Record<string, string[]> } {
	const size = difficulty > 2 ? 8 : 6;
	for (let warmup = 0; warmup < (index % 8) * 17; warmup += 1) {
		random.int(0, 999);
	}
	const words = selectWords(index, difficulty, sessionId).map(word => word.toUpperCase());
	const grid = Array.from({ length: size }, () => Array.from({ length: size }, () => UPPER_LETTERS[random.int(0, 25)]));
	const occupied = new Set<string>();
	const paths: Record<string, string[]> = {};
	const isFree = (row: number, col: number) => row >= 0 && row < size && col >= 0 && col < size && !occupied.has(`${row},${col}`);
	const place = (word: string, cells: string[]) => {
		cells.forEach(cell => occupied.add(cell));
		[...word].forEach((letter, offset) => {
			const { row, col } = parseCell(cells[offset]);
			grid[row][col] = letter;
		});
		paths[word] = cells;
	};

	for (const word of words) {
		const length = word.length;
		const orientations = [
			{ dr: 0, dc: 1, maxRow: size - 1, maxCol: size - length },
			{ dr: 1, dc: 0, maxRow: size - length, maxCol: size - 1 },
			{ dr: 1, dc: 1, maxRow: size - length, maxCol: size - length },
		];
		let placed = false;
		for (const { dr, dc, maxRow, maxCol } of random.shuffle(orientations)) {
			for (let attempt = 0; attempt < 12 && !placed; attempt += 1) {
				const row = random.int(0, Math.max(0, maxRow));
				const col = random.int(0, Math.max(0, maxCol));
				const cells = [...word].map((_, offset) => `${row + offset * dr},${col + offset * dc}`);
				if (cells.every(cell => isFree(parseCell(cell).row, parseCell(cell).col))) {
					place(word, cells);
					placed = true;
				}
			}
		}
		if (!placed) {
			for (let row = 0; row < size && !placed; row += 1) {
				for (let col = 0; col + length <= size; col += 1) {
					const cells = [...word].map((_, offset) => `${row},${col + offset}`);
					if (cells.every(cell => isFree(parseCell(cell).row, parseCell(cell).col))) {
						place(word, cells);
						placed = true;
						break;
					}
				}
			}
		}
	}
	return { size, grid, targets: words, paths };
}

export const wordMaze: GameDefinition<MazeTrial> = {
	id: 'word-maze',
	name: 'Word Maze',
	description: 'Find the words hiding along the path.',
	domain: 'attention-visual-search',
	gameVersion: '1.0.0',
	ageRange: [4, 10],
	estimatedDurationMinutes: 5,
	difficultyLevels: [1, 2, 3, 4, 5],
	instructions: ['Choose a word to find.', 'Tap letters next to each other.', 'Words can travel across, down, or diagonally.'],
	totalTrials: 3,
	createTrial: ({ index, difficulty, random, sessionId }) => {
		const maze = buildMaze(difficulty, index, sessionId, random);
		return makeTrial(index, sessionId, 'word-maze', 'attention-visual-search', difficulty, maze, maze.targets) as MazeTrial;
	},
	evaluateResponse: (trial, response) => {
		const found = Array.isArray(response) ? response : [];
		const target = trial.expectedResponse.find(word => found.includes(word));
		return { correct: found.length === trial.expectedResponse.length, score: found.length / trial.expectedResponse.length, actualResponse: found, metadata: { foundCount: found.length, lastFound: target ?? null } };
	},
	getNextDifficulty: history => history.at(-1)?.difficulty ?? 1,
};