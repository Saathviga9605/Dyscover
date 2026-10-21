import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LanguageProvider } from '../l10n';
import { STORAGE_KEY } from '../l10n/languages';
import { messages as en } from '../l10n/messages/en';
import { messages as ta } from '../l10n/messages/ta';
import { api, type ScreeningResponse, type ScreeningStatus } from '../services/apiClient';
import { ScreeningCard } from './ScreeningCard';

// Software tests with fabricated API responses; they validate rendering, not a model.
const base: ScreeningResponse = {
  child_id: 'c1',
  assessment_id: 'a1',
  assessment_completed_at: '2026-10-01T10:00:00',
  target_definition: 'x',
  feature_schema_version: 'screening-1.0',
  status: 'no_eligible_model',
  reasons: ['model was not trained on real labelled data'],
  models_considered: 0,
  model: null,
  result: null,
  observations: {
    scored_trials: 18,
    unscored_trials: 2,
    games_played: ['letter-detective'],
    domains: [],
    strengths: ['working-memory'],
    support_areas: ['orthographic-recognition'],
    speech_recorded: false,
    gaze_recorded: false,
  },
};

const eligible: ScreeningResponse = {
  ...base,
  status: 'available',
  reasons: [],
  model: {
    model_id: 'm',
    model_version: '1.2.0',
    model_name: 'Reading screen',
    output_type: 'calibrated_probability',
    feature_schema_version: 'screening-1.0',
  },
  result: {
    score: 0.27,
    score_percent: 27,
    output_type: 'calibrated_probability',
    band: 'lower',
    created_at: '2026-10-01T10:00:00',
  },
};

function renderCard(response: ScreeningResponse, language = 'en') {
  window.localStorage.setItem(STORAGE_KEY, language);
  vi.spyOn(api, 'getScreening').mockResolvedValue(response);
  return render(
    <LanguageProvider>
      <ScreeningCard childId="c1" />
    </LanguageProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('ScreeningCard', () => {
  it('shows the percentage, its meaning, model version and a text band for an eligible result', async () => {
    renderCard(eligible);
    expect(await screen.findByText('27%')).toBeTruthy();
    expect(screen.getByText(/Estimated chance that a specialist reading assessment/)).toBeTruthy();
    expect(screen.getByText(/Reading screen · v1.2.0/)).toBeTruthy();
    expect(screen.getByText(/Lower likelihood/)).toBeTruthy();
    expect(screen.getByText('Screening result: 27 percent.')).toBeTruthy();
    expect(screen.getByText(/does not rule out dyslexia/)).toBeTruthy();
  });

  it('labels an uncalibrated output as a research score, not a probability', async () => {
    renderCard({
      ...eligible,
      result: { ...eligible.result!, output_type: 'research_score', band: null },
    });
    expect(await screen.findByText(/It is not a probability/)).toBeTruthy();
    expect(screen.queryByText(/Estimated chance/)).toBeNull();
  });

  it('never shows a percentage without an eligible model, but keeps the observations', async () => {
    renderCard(base);
    expect(await screen.findByText(/No validated screening model yet/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\d+%/);
    expect(screen.getByText(/18 answered activities/)).toBeTruthy();
    expect(screen.getByText(/are not counted as mistakes/)).toBeTruthy();
    expect(screen.getByText(/qualified professional can diagnose/)).toBeTruthy();
  });

  it('renders in Tamil', async () => {
    renderCard(base, 'ta');
    expect(await screen.findByText('டிஸ்லெக்சியா அபாயத் திரையிடல்')).toBeTruthy();
    expect(screen.getByText(/இன்னும் சரிபார்க்கப்பட்ட திரையிடல் மாதிரி இல்லை/)).toBeTruthy();
  });

  it('defines every dynamic status and band message in both languages', () => {
    const statuses: ScreeningStatus[] = [
      'available',
      'no_assessment',
      'assessment_incomplete',
      'no_eligible_model',
      'unsupported_population',
      'insufficient_observations',
      'invalid_features',
    ];
    const keys = [
      ...statuses.flatMap(status => [
        `screening.status.${status}.title`,
        `screening.status.${status}.copy`,
      ]),
      ...['lower', 'moderate', 'higher'].map(band => `screening.band.${band}`),
    ];
    expect(keys.filter(key => !(key in en))).toEqual([]);
    expect(keys.filter(key => !(key in ta))).toEqual([]);
  });
});
