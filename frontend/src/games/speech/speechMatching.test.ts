import { describe, expect, it } from 'vitest';
import { normalizeText } from '../../speech/types';
import { gradeSpeechResponse, phoneticSimilarity, singleLetterName } from './speechMatching';

describe('phonetic similarity', () => {
  it('returns 1 for identical keys', () => {
    expect(phoneticSimilarity('cat', 'cat')).toBe(1);
  });

  it('counts confusable letter pairs as matches', () => {
    expect(phoneticSimilarity('pat', 'bat')).toBe(1);
    expect(phoneticSimilarity('dake', 'take')).toBe(1);
  });

  it('scores unrelated words lower', () => {
    expect(phoneticSimilarity('moon', 'star')).toBeLessThan(0.5);
  });
});

describe('single letter names', () => {
  it('expands a letter to its spoken name', () => {
    expect(singleLetterName('a')).toBe('ay');
    expect(singleLetterName('b')).toBe('bee');
    expect(singleLetterName('q')).toBe('cue');
  });

  it('returns null for non-letters', () => {
    expect(singleLetterName('cat')).toBeNull();
  });
});

describe('gradeSpeechResponse', () => {
  it('accepts the spoken letter name for a letter prompt', () => {
    const grade = gradeSpeechResponse('b', 'letter', 'bee');
    expect(grade.correct).toBe(true);
    expect(grade.matchedVia).toBe('letter-name');
  });

  it('accepts the plain letter sound for a letter prompt', () => {
    const grade = gradeSpeechResponse('b', 'letter', 'b');
    expect(grade.correct).toBe(true);
  });

  it('matches a letter pair when both letters are named', () => {
    const grade = gradeSpeechResponse('b d', 'letter-pair', 'bee dee');
    expect(grade.correct).toBe(true);
  });

  it('matches words via similarity', () => {
    const grade = gradeSpeechResponse('rabbit', 'word', 'rabbit');
    expect(grade.correct).toBe(true);
    expect(grade.transcriptSimilarity).toBe(1);
  });

  it('accepts close but inexact words via phonetic similarity', () => {
    const grade = gradeSpeechResponse('tiger', 'word', 'tiker');
    expect(grade.correct).toBe(true);
    expect(grade.matchedVia).toBe('similar');
  });

  it('matches sentences by word coverage', () => {
    const grade = gradeSpeechResponse('The red fox ran home.', 'sentence', 'the red fox ran home');
    expect(grade.correct).toBe(true);
    expect(grade.matchedVia).toBe('word-coverage');
  });

  it('rejects clearly wrong answers', () => {
    const grade = gradeSpeechResponse('planet', 'word', 'mother');
    expect(grade.correct).toBe(false);
    expect(grade.matchedVia).toBe('none');
  });

  it('handles an empty transcript without throwing', () => {
    const grade = gradeSpeechResponse('cat', 'word', '');
    expect(grade.correct).toBe(false);
  });
});

describe('non-English language guard', () => {
  it('disables phonetic similarity outside English', () => {
    expect(phoneticSimilarity('pat', 'bat')).toBe(1);
    expect(phoneticSimilarity('pat', 'bat', 'ta')).toBe(-1);
  });

  it('keeps Tamil script intact when normalizing', () => {
    expect(normalizeText('கண்ணாடி', 'ta')).toBe('கண்ணாடி');
  });

  it('does not reduce Tamil to empty text under the English filter', () => {
    expect(normalizeText('கண்ணாடி', 'en')).toBe('');
  });

  it('strips diacritics in English normalization', () => {
    expect(normalizeText('café', 'en')).toBe('cafe');
    expect(normalizeText('café', 'ta')).toBe('café');
  });

  it('does not apply English letter-name aliases to non-English prompts', () => {
    expect(singleLetterName('b')).toBe('bee');
    expect(singleLetterName('b', 'ta')).toBeNull();
  });

  it('rejects a letter name that only matches via English phonetics', () => {
    const grade = gradeSpeechResponse('b', 'letter', 'bee', 'ta');
    expect(grade.correct).toBe(false);
    expect(grade.matchedVia).toBe('none');
  });

  it('matches Tamil prompts via exact normalized similarity', () => {
    const grade = gradeSpeechResponse('கண்ணாடி', 'word', 'கண்ணாடி', 'ta');
    expect(grade.correct).toBe(true);
    expect(grade.matchedVia).toBe('exact');
  });
});