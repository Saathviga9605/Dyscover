import type { SeededRandom } from './types';

export function createSeededRandom(seed = Math.floor(Math.random() * 2147483647)): SeededRandom {
  let value = seed % 2147483647 || 1;
  const next = () => { value = value * 16807 % 2147483647; return (value - 1) / 2147483646; };
  return { next, int: (min, max) => Math.floor(next() * (max - min + 1)) + min, pick: <T>(items: T[]) => items[Math.floor(next() * items.length)], shuffle: <T>(items: T[]) => [...items].sort(() => next() - .5) };
}

export function createId(prefix: string): string { return `${prefix}_${crypto.randomUUID()}`; }
