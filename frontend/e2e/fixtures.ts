import AxeBuilder from '@axe-core/playwright';
import { expect, type APIRequestContext, type Page } from '@playwright/test';

export const PASSWORD = 'e2e-password-123';

export function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

export async function registerViaUi(
  page: Page,
  role: 'parent' | 'educator',
  name: string
): Promise<string> {
  const email = uniqueEmail(role);
  await page.goto('/register');
  await page.getByLabel('Display name').fill(name);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  if (role === 'educator') await page.getByLabel('Educator').check();
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(
    role === 'educator' ? /\/educator\/dashboard/ : /\/parent\/dashboard/
  );
  return email;
}

export async function loginViaUi(page: Page, email: string, password = PASSWORD): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
}

export async function createChildViaUi(page: Page, name: string): Promise<void> {
  await page.goto('/parent/dashboard');
  const nameField = page.getByLabel('Name or nickname');
  const addButton = page.getByRole('button', { name: 'Add a child' });
  // Wait for the child list to load: either the first-child form or the add button.
  await expect(nameField.or(addButton).first()).toBeVisible();
  if (!(await nameField.isVisible())) await addButton.click();
  await page.getByLabel('Name or nickname').fill(name);
  await page.getByRole('button', { name: 'Create profile' }).click();
  await expect(page.getByRole('button', { name: new RegExp(name) })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
}

/** Independent API session (bearer token) used to verify what the UI persisted. */
export async function apiAs(request: APIRequestContext, email: string) {
  const login = await request.post('/api/auth/login', { data: { email, password: PASSWORD } });
  expect(login.ok()).toBeTruthy();
  const { access_token: token } = (await login.json()) as { access_token: string };
  const headers = { Authorization: `Bearer ${token}` };
  return {
    get: async <T>(path: string): Promise<T> => {
      const response = await request.get(`/api${path}`, { headers });
      expect(response.ok(), `GET ${path} -> ${response.status()}`).toBeTruthy();
      return (await response.json()) as T;
    },
  };
}

/**
 * Replaces the browser speech-recognition API with a deterministic stand-in that
 * "hears" the prompt shown on screen. Real recognition cannot run headless; this
 * mocks only the browser capability, not Dyscover's code.
 */
export async function stubSpeechRecognition(page: Page): Promise<void> {
  await page.addInitScript(() => {
    class FakeRecognition {
      lang = 'en-US';
      continuous = false;
      interimResults = true;
      maxAlternatives = 1;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onspeechstart: (() => void) | null = null;
      onaudiostart: (() => void) | null = null;
      private timer: number | undefined;
      start() {
        this.timer = window.setTimeout(() => {
          const prompt = document.querySelector('.speech-target')?.textContent?.trim() ?? 'cat';
          this.onspeechstart?.();
          const alternative = { transcript: prompt, confidence: 0.92 };
          const row = Object.assign([alternative], { isFinal: true });
          this.onresult?.({ results: [row] });
          this.onend?.();
        }, 300);
      }
      stop() {
        window.clearTimeout(this.timer);
      }
      abort() {
        window.clearTimeout(this.timer);
      }
    }
    Object.defineProperty(window, 'SpeechRecognition', {
      value: FakeRecognition,
      configurable: true,
    });
    Object.defineProperty(window, 'webkitSpeechRecognition', {
      value: FakeRecognition,
      configurable: true,
    });
  });
}

export async function expectNoSeriousA11yViolations(page: Page, context: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  const serious = results.violations.filter(v => v.impact === 'serious' || v.impact === 'critical');
  const details = serious.flatMap(v =>
    v.nodes.map(
      n =>
        `${v.id}: ${n.target.join(' ')} | ${n.any[0]?.message ?? n.failureSummary ?? ''}`.split(
          String.fromCharCode(10)
        )[0]
    )
  );
  expect(details, `${context}: serious/critical axe violations`).toEqual([]);
}
