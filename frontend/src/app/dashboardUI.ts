import type { ProgressResponse, Recommendation } from '../services/apiClient';

const DOMAIN_LABELS: Record<string, string> = {
	'visual-symbol-discrimination': 'Visual symbol discrimination',
	'orthographic-recognition': 'Orthographic recognition',
	'phonological-awareness': 'Phonological awareness',
	'working-memory': 'Working memory',
	'sequencing': 'Sequencing',
	'attention-visual-search': 'Attention / visual search',
	'reading-fluency': 'Reading fluency',
	'interaction-behavior': 'Interaction behavior',
};

export function domainLabel(domain: string): string {
	const known = DOMAIN_LABELS[domain];
	if (known) return known;
	return domain.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, match => match.toUpperCase());
}

export function formatPercent(accuracy?: number | null): string {
	if (typeof accuracy !== 'number') return 'Observed';
	return `${Math.round(accuracy * 100)}%`;
}

export function dedupeRecommendations(recs: Recommendation[]): Recommendation[] {
	const seen = new Set<string>();
	const result: Recommendation[] = [];
	for (const rec of recs) {
		const key = rec.target_domain_label ?? rec.target_domain ?? rec.kind;
		if (key === null || key === undefined) {
			result.push(rec);
			continue;
		}
		if (seen.has(key)) continue;
		seen.add(key);
		result.push(rec);
	}
	return result;
}

export interface ComparisonRow {
	label: string;
	deltaText: string;
}

export function comparisonRows(progress: ProgressResponse | null | undefined): ComparisonRow[] {
	const comparison = progress?.comparison;
	if (!comparison) return [];
	return Object.entries(comparison.domains)
		.map(([domain, point]) => ({
			label: domainLabel(domain),
			deltaText: `${point.delta >= 0 ? '+' : ''}${Math.round(point.delta * 100)}% vs first screening`,
		}))
		.sort((a, b) => a.label.localeCompare(b.label));
}