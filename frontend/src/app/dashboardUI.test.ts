import { describe, expect, it } from 'vitest';
import { comparisonRows, dedupeRecommendations, domainLabel, formatPercent } from './dashboardUI';
import type { ProgressResponse, Recommendation } from '../services/apiClient';
import { progressMessage } from '../services/childPersonalization';

const PROHIBITED = ['risk', 'diagno', 'disorder', 'impairment', 'disabl', 'probab', 'percentile', 'clinical', 'deficit', 'delayed'];

function rec(domain: string, label: string, gameId: string): Recommendation {
	return {
		game_id: gameId,
		target_domain: domain,
		target_domain_label: label,
		priority: 20,
		reason: `Recent activity suggests more practice with ${label.toLowerCase()} activities may be helpful.`,
		category: 'practice_opportunity',
		kind: 'game_activity',
	};
}

describe('dashboard helpers', () => {
	it('deduplicates recommendations that share a target domain, keeping the first', () => {
		const visual = rec('visual-symbol-discrimination', 'Visual symbol discrimination', 'letter-detective');
		const visualAgain = rec('visual-symbol-discrimination', 'Visual symbol discrimination', 'mirror-match');
		const orthographic = rec('orthographic-recognition', 'Orthographic recognition', 'word-flash');
		const result = dedupeRecommendations([visual, visualAgain, orthographic]);
		expect(result).toHaveLength(2);
		expect(result.map(item => item.game_id)).toEqual(['letter-detective', 'word-flash']);
	});

	it('collapses identical neutral recommendations but keeps them distinct from game activities', () => {
		const neutral: Recommendation = { game_id: null, target_domain: null, priority: 0, reason: 'Not enough completed activity has been observed yet to make activity suggestions.', category: 'insufficient_data', kind: 'neutral' };
		const activity = rec('visual-symbol-discrimination', 'Visual symbol discrimination', 'letter-detective');
		expect(dedupeRecommendations([neutral, neutral])).toHaveLength(1);
		expect(dedupeRecommendations([neutral, activity, neutral])).toHaveLength(2);
	});

	it('maps domain ids to parent-friendly labels', () => {
		expect(domainLabel('visual-symbol-discrimination')).toBe('Visual symbol discrimination');
		expect(domainLabel('working-memory')).toBe('Working memory');
		expect(domainLabel('attention-visual-search')).toBe('Attention / visual search');
		expect(domainLabel('some-key')).toBe('Some Key');
	});

	it('formats observed accuracy as a percent', () => {
		expect(formatPercent(1)).toBe('100%');
		expect(formatPercent(0.667)).toBe('67%');
		expect(formatPercent(2)).toBe('200%');
		expect(formatPercent(null)).toBe('Observed');
		expect(formatPercent(undefined)).toBe('Observed');
	});

	it('shows no comparison while only one screening exists', () => {
		const single: ProgressResponse = { child_id: 'c', engine_version: 'v', mode: 'research', points: [{ assessment_id: 'a1', domains: {} }], comparison: null, note: null };
		expect(comparisonRows(single)).toEqual([]);
		expect(progressMessage(single)).toBe('Complete another screening to see activity progress over time.');
	});

	it('compares multiple screenings with labelled deltas', () => {
		const progress: ProgressResponse = {
			child_id: 'c',
			engine_version: 'v',
			mode: 'research',
			points: [
				{ assessment_id: 'a1', domains: { 'visual-symbol-discrimination': 0.6 } },
				{ assessment_id: 'a2', domains: { 'visual-symbol-discrimination': 0.65 } },
			],
			comparison: {
				earliest_assessment_id: 'a1',
				latest_assessment_id: 'a2',
				domains: {
					'visual-symbol-discrimination': { earliest_accuracy: 0.6, latest_accuracy: 0.65, delta: 0.05 },
					'working-memory': { earliest_accuracy: 0.9, latest_accuracy: 0.8, delta: -0.1 },
				},
			},
			note: null,
		};
		const rows = comparisonRows(progress);
		expect(rows).toEqual([
			{ label: 'Visual symbol discrimination', deltaText: '+5% vs first screening' },
			{ label: 'Working memory', deltaText: '-10% vs first screening' },
		]);
		expect(progressMessage(progress)).toBeNull();
	});

	it('never emits clinical, risk, or probability language on the dashboard', () => {
		const texts = [
			domainLabel('visual-symbol-discrimination'),
			formatPercent(0.8),
			...dedupeRecommendations([
				rec('visual-symbol-discrimination', 'Visual symbol discrimination', 'letter-detective'),
				rec('orthographic-recognition', 'Orthographic recognition', 'word-flash'),
			]).flatMap(item => [item.reason, item.target_domain_label ?? '']),
			...comparisonRows({
				child_id: 'c', engine_version: 'v', mode: 'research', points: [], comparison: {
					earliest_assessment_id: 'a1', latest_assessment_id: 'a2',
					domains: { 'visual-symbol-discrimination': { earliest_accuracy: 0.5, latest_accuracy: 0.6, delta: 0.1 } },
				}, note: null,
			}).flatMap(row => [row.label, row.deltaText]),
		];
		const lowered = texts.join(' ').toLowerCase();
		for (const term of PROHIBITED) {
			expect(lowered).not.toContain(term);
		}
	});
});