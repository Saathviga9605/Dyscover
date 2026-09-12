import type { AoiRegion, RegionRef } from './types';

export interface AoiSpec {
  type: AoiRegion['type'];
  label: string;
  selector: string;
}

const GAME_AOI_SPECS: Record<string, AoiSpec[]> = {
  'letter-detective': [
    { type: 'target', label: 'target', selector: '.detective-clue' },
    { type: 'option', label: 'option', selector: '.letter-option' },
    { type: 'neutral', label: 'board', selector: '.detective-board' },
  ],
  'mirror-match': [
    { type: 'target', label: 'target', selector: '.mirror-example' },
    { type: 'option', label: 'option', selector: '.mirror-option' },
    { type: 'neutral', label: 'board', selector: '.mirror-board' },
  ],
  'word-flash': [
    { type: 'target', label: 'target', selector: '.flash-stimulus' },
    { type: 'option', label: 'option', selector: '.word-option' },
    { type: 'neutral', label: 'board', selector: '.flash-board' },
  ],
  'sequence-quest': [
    { type: 'target', label: 'display', selector: '.sequence-display' },
    { type: 'option', label: 'option', selector: '.sequence-option' },
    { type: 'neutral', label: 'board', selector: '.sequence-board' },
  ],
  'word-maze': [
    { type: 'target', label: 'target', selector: '.maze-target' },
    { type: 'option', label: 'option', selector: '.maze-cell' },
    { type: 'instruction', label: 'maze-help', selector: '.maze-help' },
  ],
};

export function specsForGame(gameId: string): AoiSpec[] {
  return GAME_AOI_SPECS[gameId] ?? [];
}

export function captureRegions(gameId: string, root: ParentNode | null = document): AoiRegion[] {
  const specs = specsForGame(gameId);
  if (!root) return [];
  const regions: AoiRegion[] = [];
  for (const spec of specs) {
    const elements = Array.from(root.querySelectorAll<HTMLElement>(spec.selector));
    if (!elements.length) {
      regions.push({ label: spec.label, type: spec.type, left: 0, top: 0, width: 0, height: 0, available: false });
      continue;
    }
    for (const element of elements) {
      const rect = element.getBoundingClientRect();
      regions.push({
        label: spec.label,
        type: spec.type,
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
        available: rect.width > 0 && rect.height > 0,
        elementId: element.getAttribute('data-aoi-id') ?? undefined,
      });
    }
  }
  return regions;
}

export function regionForPoint(x: number, y: number, regions: AoiRegion[]): RegionRef | null {
  for (const region of regions) {
    if (!region.available) continue;
    if (x >= region.left && x <= region.left + region.width && y >= region.top && y <= region.top + region.height) {
      return { type: region.type, label: region.label, elementId: region.elementId };
    }
  }
  return null;
}