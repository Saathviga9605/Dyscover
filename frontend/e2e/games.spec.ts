import { expect, test, type Page } from '@playwright/test';
import { apiAs, createChildViaUi, registerViaUi, stubSpeechRecognition } from './fixtures';

// Full game runs include real feedback delays between trials.
test.describe.configure({ timeout: 300_000 });

const VISUAL_TRIALS = { 'letter-detective': 5, 'mirror-match': 5, 'word-flash': 5, 'sequence-quest': 4, 'word-maze': 3 };

/**
 * Plays whatever game screen is showing until the run returns to the parent
 * dashboard. Answers are deliberately naive (first option, finish maze early):
 * the test checks that every game starts, accepts input, completes, and that
 * the server stores its trials — not the child's score.
 */
async function playUntilDashboard(page: Page, seenGames: Set<string>): Promise<void> {
  for (let step = 0; step < 400; step += 1) {
    if (/\/parent\/dashboard/.test(page.url())) return;
    const heading = page.locator('.game-intro-card h1, .game-shell h1, .game-overlay-page h1').first();
    if (await heading.isVisible().catch(() => false)) seenGames.add((await heading.textContent())?.trim() ?? '');

    const start = page.getByRole('button', { name: "Let's go" });
    const next = page.getByRole('button', { name: 'Continue the adventure' });
    const finishMaze = page.getByRole('button', { name: "I'm finished" });
    const sequence = page.locator('.sequence-option:not([disabled])');
    const option = page.locator('.letter-option:not([disabled]), .mirror-option:not([disabled]), .word-option:not([disabled])');

    // Elements detach between trials; a missed click simply retries on the next step.
    const click = (locator: typeof start) => locator.click({ timeout: 2_000 }).catch(() => undefined);
    if (await start.isEnabled({ timeout: 50 }).catch(() => false)) await click(start);
    else if (await next.isVisible({ timeout: 50 }).catch(() => false)) await click(next);
    else if (await finishMaze.isVisible({ timeout: 50 }).catch(() => false)) await click(finishMaze);
    else if ((await sequence.count()) > 0) await click(sequence.first());
    else if ((await option.count()) > 0) await click(option.first());
    else await page.waitForTimeout(150); // stimulus presentation / feedback / speech listening
  }
  throw new Error(`Game run did not finish; last URL ${page.url()}`);
}

test('all five visual games run end to end and their trials are stored', async ({ page, request }) => {
  const email = await registerViaUi(page, 'parent', 'Vee Parent');
  await createChildViaUi(page, 'Ava');
  await page.goto('/child/home');
  await expect(page.getByRole('heading', { name: 'Hello, Ava!' })).toBeVisible();
  await page.goto('/child/assessment');
  await page.getByRole('link', { name: /Play the visual adventures/ }).click();
  await expect(page).toHaveURL(/\/child\/assessment\/visual/);

  const seen = new Set<string>();
  await playUntilDashboard(page, seen);

  const api = await apiAs(request, email);
  const children = await api.get<Array<{ id: string }>>('/children');
  // Trials are persisted asynchronously right before navigation; allow them to land.
  await expect
    .poll(async () => (await api.get<{ trials: { count: number } }>('/privacy/data-summary')).trials.count)
    .toBe(Object.values(VISUAL_TRIALS).reduce((a, b) => a + b, 0));
  const assessments = await api.get<Array<{ status: string }>>(`/children/${children[0].id}/assessments`);
  expect(assessments).toHaveLength(1);
  expect(assessments[0].status).toBe('completed');
  const profile = await api.get<{ skills: Array<{ domain: string; trial_count: number }> }>(
    `/personalization/children/${children[0].id}/profile`
  );
  const counts = Object.fromEntries(profile.skills.map(skill => [skill.domain, skill.trial_count]));
  expect(counts['visual-symbol-discrimination']).toBe(VISUAL_TRIALS['letter-detective'] + VISUAL_TRIALS['mirror-match']);
  expect(counts['orthographic-recognition']).toBe(VISUAL_TRIALS['word-flash']);
  expect(counts['working-memory']).toBe(VISUAL_TRIALS['sequence-quest']);
  expect(counts['attention-visual-search']).toBe(VISUAL_TRIALS['word-maze']);

  // The parent dashboard now shows observations for the completed run, without diagnostic language.
  await expect(page.getByRole('heading', { name: 'What we observed' }).or(page.locator('.observed-list').first())).toBeVisible();
  await expect(page.locator('body')).not.toContainText(/diagnosed|has dyslexia/i);
});

test('all three speech games run with consent and store speech observations', async ({ page, request }) => {
  await stubSpeechRecognition(page);
  const email = await registerViaUi(page, 'parent', 'Sol Parent');
  await createChildViaUi(page, 'Leo');
  await page.goto('/child/assessment/speech');

  // Without consent the activity cannot start (and the microphone is never used).
  const start = page.getByRole('button', { name: "Let's go" });
  await expect(start).toBeDisabled();
  await expect(page.getByText('A grown-up needs to allow the microphone')).toBeVisible();
  await page.getByRole('button', { name: 'Yes, let this activity listen' }).click();

  const seen = new Set<string>();
  await playUntilDashboard(page, seen);

  const api = await apiAs(request, email);
  await expect.poll(async () => (await api.get<{ speech_sessions: { count: number } }>('/privacy/data-summary')).speech_sessions.count).toBeGreaterThan(0);
  const summary = await api.get<{ trials: { count: number }; speech_sessions: { count: number } }>('/privacy/data-summary');
  expect(summary.speech_sessions.count).toBe(summary.trials.count);
  // Every speech trial (across all three games) has its own speech session with recognition features.
  const children = await api.get<Array<{ id: string }>>('/children');
  const [assessment] = await api.get<Array<{ id: string; status: string }>>(
    `/children/${children[0].id}/assessments`
  );
  expect(assessment.status).toBe('completed');
  const modality = await api.get<{
    speech: { recorded: boolean; trial_count: number; trial_coverage: number; asr_available: number };
  }>(`/assessments/${assessment.id}/modality-summary`);
  expect(modality.speech.recorded).toBe(true);
  expect(modality.speech.trial_coverage).toBe(1);
  expect(modality.speech.asr_available).toBe(modality.speech.trial_count);
  expect(modality.speech.trial_count).toBeGreaterThanOrEqual(9);
});

test('a child cannot start activities until an adult picks a profile', async ({ page }) => {
  await registerViaUi(page, 'parent', 'New Parent');
  await page.goto('/child/assessment/visual');
  await expect(page.getByRole('heading', { name: 'Let’s make a profile first' })).toBeVisible();
  await page.getByRole('link', { name: 'Create a child profile' }).click();
  await expect(page).toHaveURL(/\/parent\/dashboard/);
});
