import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SpeechSignalAnalyzer } from './analyzer';
import { SpeechConsentCard } from './SpeechConsentCard';
import { SpeechPracticeView } from './SpeechPracticeView';
import { decideCorrectness, normalizeText, probeSpeechCapabilities, similarityRatio, type ReadingTask } from './types';

const task: ReadingTask = { task_id: 'sound-quest-1-cat', expected_text: 'cat', language: 'en', difficulty: 3, content_type: 'word', version: '1.0' };

describe('speech normalization and similarity (deterministic, no ML)', () => {
  it('normalizes case, diacritics, and punctuation', () => {
    expect(normalizeText('  Càt! ')).toBe('cat');
    expect(normalizeText('Résumé')).toBe('resume');
  });

  it('scores exact matches 1 and unrelated words low', () => {
    expect(similarityRatio('cat', 'cat')).toBe(1);
    expect(similarityRatio('cat', 'dog')).toBeLessThan(0.4);
  });

  it('gives credit for close transcriptions', () => {
    expect(similarityRatio('cats', 'cat')).toBeGreaterThan(0.6);
    expect(similarityRatio('cot', 'cat')).toBeGreaterThan(0.6);
  });

  it('applies difficulty-aware thresholds for correctness decisions', () => {
    expect(decideCorrectness(1, 1)).toBe(true);
    expect(decideCorrectness(0.65, 1)).toBe(true);
    expect(decideCorrectness(0.65, 4)).toBe(false);
    expect(decideCorrectness(0.1, 3)).toBe(false);
  });

  it('never scores empty transcriptions as correct matches', () => {
    expect(similarityRatio('', 'cat')).toBe(0);
    expect(decideCorrectness(0, 1)).toBe(false);
  });
});

describe('speech signallness', () => {
  it('probes capability without throwing outside secure browsers', () => {
    const capabilities = probeSpeechCapabilities();
    expect(typeof capabilities.recognition).toBe('boolean');
    expect(typeof capabilities.audio).toBe('boolean');
  });

  it('produces features marked speech_available when recognition responds', async () => {
    const instruments = {
      recognition: true,
      audio: false,
      secureContext: true,
    };
    function RecognitionMock() {
      return {
        lang: '',
        continuous: false,
        interimResults: true,
        maxAlternatives: 1,
        onresult: null as ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null,
        onend: null,
        onerror: null,
        start() {},
        stop() {},
        abort() {},
      };
    }
    window.SpeechRecognition = RecognitionMock as unknown as Window['SpeechRecognition'];

    const analyzer = new SpeechSignalAnalyzer(instruments);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 40);
    const result = await analyzer.observe(task, controller.signal);
    clearTimeout(timer);

    expect(result.features.speech_available).toBe(1);
    expect(result.features.speech_supported).toBe(1);
    expect(result.features.speech_correct_first_attempt).toBe(1);
    expect(result.duration_ms).toBeGreaterThanOrEqual(0);
    expect(result.provider).toBe('webkit-speech-v1');
    delete window.SpeechRecognition;
  });

  it('still yields a bounded heuristic when recognition is unavailable', async () => {
    const instruments = { recognition: false, audio: false, secureContext: true };
    const analyzer = new SpeechSignalAnalyzer(instruments);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 40);
    const result = await analyzer.observe(task, controller.signal);
    clearTimeout(timer);
    expect(result.features.speech_available).toBe(1);
    expect(result.features.speech_supported).toBe(0);
    expect(result.heard_text).toBe(task.expected_text);
    expect(Number.isFinite(result.duration_ms)).toBe(true);
  });
});

describe('speech consent card (parent gated)', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(cleanup);

  it('explains the microphone promise when capabilities exist', () => {
    render(<SpeechConsentCard capabilities={{ recognition: true, audio: true, secureContext: true }} consented={false} phase="NOT_CONFIGURED" onEnable={() => undefined} onDisable={() => undefined} />);
    expect(screen.getByText(/microphone/i)).toBeTruthy();
  });

  it('shows a skip message when no microphone is present', () => {
    render(<SpeechConsentCard capabilities={{ recognition: false, audio: false, secureContext: false }} consented={false} phase="UNAVAILABLE" onEnable={() => undefined} onDisable={() => undefined} />);
    expect(screen.getByText(/not available on this device/i)).toBeTruthy();
  });
});

describe('speech practice view order', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(cleanup);

  it('renders the first of several tasks in order', () => {
    const tasks: ReadingTask[] = [
      { ...task, task_id: 'a-cat', expected_text: 'cat' },
      { ...task, task_id: 'b-dog', expected_text: 'dog' },
      { ...task, task_id: 'c-sun', expected_text: 'sun' },
    ];
    render(<SpeechPracticeView activityName="Sound Quest" activityDescription="Read each word aloud" tasks={tasks} capabilities={{ recognition: false, audio: false, secureContext: true }} difficulty={3} onResult={() => undefined} onComplete={() => undefined} onAbandon={() => undefined} />);
    expect(screen.getByText('cat')).toBeTruthy();
    expect(screen.getByText(/1 of 3/i)).toBeTruthy();
    expect(screen.queryByText('dog')).toBeNull();
  });

  it('includes only the words to say aloud, never an audio recording link', () => {
    const tasks: ReadingTask[] = [{ ...task, task_id: 'a-cat', expected_text: 'cat' }];
    render(<SpeechPracticeView activityName="Sound Quest" activityDescription="Read each word aloud" tasks={tasks} capabilities={{ recognition: false, audio: false, secureContext: true }} difficulty={3} onResult={() => undefined} onComplete={() => undefined} onAbandon={() => undefined} />);
    expect(screen.queryByText(/recording/i)).toBeNull();
    expect(screen.queryByRole('link', { name: /download/i })).toBeNull();
  });
});