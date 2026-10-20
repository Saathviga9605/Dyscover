import { describe, expect, it } from 'vitest';
import { messages as en } from './messages/en';
import { messages as ta } from './messages/ta';

// Every non-test source file, as raw text (resolved by Vite at test time).
const sources = import.meta.glob<string>(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

// Static keys passed to t('...'). Dynamic keys (template literals) are checked
// where they are built, e.g. domain labels fall back to English text.
const usedKeys = new Set(
  Object.values(sources).flatMap(text =>
    [...text.matchAll(/\bt\(\s*'([a-zA-Z0-9_.-]+)'/g)].map(match => match[1])
  )
);

describe('message catalogs', () => {
  it('scans the application sources', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(40);
    expect(usedKeys.size).toBeGreaterThan(300);
  });

  it('define every key the interface uses (English)', () => {
    const missing = [...usedKeys].filter(key => !(key in en)).sort();
    expect(missing).toEqual([]);
  });

  it('translate every key the interface uses into Tamil', () => {
    const missing = [...usedKeys].filter(key => !(key in ta)).sort();
    expect(missing).toEqual([]);
  });

  it('keep interpolation placeholders consistent between languages', () => {
    const placeholders = (text: string) =>
      [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
    const mismatched = Object.keys(ta).filter(
      key => key in en && placeholders(en[key]).join(',') !== placeholders(ta[key]).join(',')
    );
    expect(mismatched).toEqual([]);
  });
});
