import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LanguageProvider } from '../l10n';
import { STORAGE_KEY } from '../l10n/languages';
import { messages as en } from '../l10n/messages/en';
import { messages as ta } from '../l10n/messages/ta';
import {
  api,
  ApiError,
  type ResearchOverview,
  type ResearchPredictionResponse,
  type ResearchStatus,
  type ScreeningResponse,
} from '../services/apiClient';
import { ResearchPredictor } from './ResearchPredictor';
import { ResearchLink, ScreeningCard } from './ScreeningCard';

// Rendering tests with fabricated API responses. The real model/API path is covered by
// backend tests (tests/test_research_predictor.py) and the Playwright research run.
vi.mock('../auth', () => ({ useAuth: () => ({ user: { role: 'parent' } }) }));
vi.mock('./ChildContext', () => ({
  useChildren: () => ({ children: [{ id: 'c1', display_name: 'Ava' }] }),
}));

const model = {
  model_id: 'dyscover-research-synthetic',
  model_version: '1.0.0',
  model_name: 'Dyscover synthetic research predictor (gradient_boosting)',
  algorithm: 'gradient_boosting',
  designation: 'synthetic_research' as const,
  training_data: 'synthetic' as const,
  output_type: 'calibrated_probability' as const,
  target_id: 'synthetic_reading_difficulty_profile_v1',
  target_definition: 'Synthetic target: simulator setting.',
  feature_schema_version: 'screening-1.0',
  artifact_sha256: 'a'.repeat(64),
  created_at: '2026-10-21T00:00:00',
  synthetic_test_metrics: {
    roc_auc: 0.99,
    pr_auc: 0.99,
    brier: 0.03,
    sensitivity: 0.87,
    specificity: 0.98,
  },
  synthetic_test_counts: { rows: 320, participants: 160 },
  inputs: { min_scored_trials: 15, languages: ['en'], age_min: 4, age_max: 10 },
};

const overview: ResearchOverview = {
  label: 'x',
  notice: 'x',
  child_id: 'c1',
  model,
  model_problems: [],
  assessments: [
    {
      assessment_id: 'a1',
      status: 'completed',
      language: 'en',
      created_at: '2026-10-21T10:00:00',
      completed_at: '2026-10-21T10:10:00',
      has_prediction: false,
    },
  ],
};

const available: ResearchPredictionResponse = {
  label: 'x',
  notice: 'x',
  child_id: 'c1',
  assessment_id: 'a1',
  status: 'available',
  reasons: [],
  notes: [],
  model,
  observations: {
    scored_trials: 22,
    unscored_trials: 0,
    games_played: [],
    speech_recorded: false,
    gaze_recorded: false,
  },
  features: [
    {
      name: 'overall_accuracy',
      modality: 'behavior',
      value: 0.5,
      available: true,
      training_median: 0.8,
      outside_training_range: false,
      score_change_if_typical: -0.31,
    },
    {
      name: 'speech_error_rate',
      modality: 'speech',
      value: null,
      available: false,
      training_median: null,
      outside_training_range: null,
      score_change_if_typical: null,
    },
  ],
  result: {
    score: 0.734,
    score_percent: 73,
    output_type: 'calibrated_probability',
    created_at: 'x',
  },
};

function renderPage(language = 'en') {
  window.localStorage.setItem(STORAGE_KEY, language);
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <ResearchPredictor />
      </MemoryRouter>
    </LanguageProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('ResearchPredictor', () => {
  it('runs the model for the chosen session and shows its labelled output', async () => {
    vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    const run = vi.spyOn(api, 'runResearchPrediction').mockResolvedValue(available);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Run the research model' }));
    expect(await screen.findByTestId('research-score')).toHaveProperty('textContent', '73%');
    expect(run).toHaveBeenCalledWith('c1', 'a1');
    expect(screen.getByText('Synthetic research score:')).toBeTruthy();
    expect(screen.getByText(/NOT a real-child dyslexia probability/)).toBeTruthy();
    expect(screen.getByText(/cannot confirm or rule out dyslexia/)).toBeTruthy();
    expect(screen.getByText('raises it by 31 points')).toBeTruthy();
    expect(
      screen.getByText(/Not recorded, so not used or estimated: Reading-aloud errors/)
    ).toBeTruthy();
    expect(screen.getByText(/ROC-AUC 0.990 on 160 simulated participants/)).toBeTruthy();
  });

  it('labels an uncalibrated output as a research score, not a probability', async () => {
    vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    vi.spyOn(api, 'runResearchPrediction').mockResolvedValue({
      ...available,
      result: { ...available.result!, output_type: 'research_score' },
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Run the research model' }));
    expect(await screen.findByText('Research score (not a probability):')).toBeTruthy();
    expect(screen.queryByText('Synthetic research score:')).toBeNull();
  });

  it('explains statuses without showing any score', async () => {
    vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    vi.spyOn(api, 'runResearchPrediction').mockResolvedValue({
      ...available,
      status: 'insufficient_observations',
      reasons: ['missing (not estimated): domain_working-memory_accuracy'],
      features: [],
      result: null,
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Run the research model' }));
    expect(await screen.findByText('Not enough observations')).toBeTruthy();
    expect(screen.getByText(/missing \(not estimated\)/)).toBeTruthy();
    expect(screen.queryByTestId('research-score')).toBeNull();
  });

  it('shows an error state when inference fails', async () => {
    vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    vi.spyOn(api, 'runResearchPrediction').mockRejectedValue(new Error('boom'));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Run the research model' }));
    expect(await screen.findByText(/could not be run/)).toBeTruthy();
  });

  it('says research mode is off when the server returns 404', async () => {
    vi.spyOn(api, 'getResearchOverview').mockRejectedValue(
      new ApiError(404, 'Not found', undefined)
    );
    renderPage();
    expect(await screen.findByText('Research mode is not enabled on this server')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Run the research model' })).toBeNull();
  });

  it('renders in Tamil', async () => {
    vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    renderPage('ta');
    expect(await screen.findByText('செயற்கை ஆய்வு முன்கணிப்பான்')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'ஆய்வு மாதிரியை இயக்கு' })).toBeTruthy();
  });

  it('defines every status and feature message in both languages', () => {
    const statuses: ResearchStatus[] = [
      'available',
      'no_research_model',
      'assessment_incomplete',
      'unsupported_population',
      'insufficient_observations',
      'invalid_features',
      'model_version_conflict',
    ];
    const keys = statuses.flatMap(status => [
      `researchPredictor.status.${status}.title`,
      `researchPredictor.status.${status}.copy`,
    ]);
    const featureKeys = Object.keys(en).filter(key => key.startsWith('researchPredictor.feature.'));
    expect(featureKeys).toHaveLength(13);
    expect([...keys, ...featureKeys].filter(key => !(key in en) || !(key in ta))).toEqual([]);
  });
});

describe('parent screening card stays separate from research output', () => {
  const noModel: ScreeningResponse = {
    child_id: 'c1',
    assessment_id: 'a1',
    assessment_completed_at: null,
    target_definition: 'x',
    feature_schema_version: 'screening-1.0',
    status: 'no_eligible_model',
    reasons: [],
    models_considered: 0,
    model: null,
    result: null,
    observations: {
      scored_trials: 22,
      unscored_trials: 0,
      games_played: [],
      domains: [],
      strengths: [],
      support_areas: [],
      speech_recorded: false,
      gaze_recorded: false,
    },
  };

  it('never shows a research score on the screening card, only a link when enabled', async () => {
    vi.spyOn(api, 'getScreening').mockResolvedValue(noModel);
    const overviewSpy = vi.spyOn(api, 'getResearchOverview').mockResolvedValue(overview);
    const prediction = vi.spyOn(api, 'runResearchPrediction');
    render(
      <LanguageProvider>
        <MemoryRouter>
          <ScreeningCard childId="c1" />
          <ResearchLink childId="c1" />
        </MemoryRouter>
      </LanguageProvider>
    );
    expect(await screen.findByRole('link', { name: /synthetic research predictor/ })).toBeTruthy();
    expect(await screen.findByText(/No validated screening model yet/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\d+%/);
    expect(overviewSpy).toHaveBeenCalled();
    expect(prediction).not.toHaveBeenCalled();
  });

  it('hides the research link when research mode is off', async () => {
    vi.spyOn(api, 'getResearchOverview').mockRejectedValue(
      new ApiError(404, 'Not found', undefined)
    );
    render(
      <LanguageProvider>
        <MemoryRouter>
          <ResearchLink childId="c1" />
        </MemoryRouter>
      </LanguageProvider>
    );
    await waitFor(() => expect(api.getResearchOverview).toHaveBeenCalled());
    expect(screen.queryByRole('link')).toBeNull();
  });
});
