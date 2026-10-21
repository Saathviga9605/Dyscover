import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * End-to-end tests run the real FastAPI backend (fresh throw-away SQLite
 * database, migrations applied at startup) behind the real Vite dev server.
 * Only the Lexi model is replaced, at the provider boundary, by the
 * test-only echo provider (refused outside APP_ENV=test). Research mode is on so
 * the synthetic research predictor can be exercised against the real model.
 */
const API_PORT = Number(process.env.E2E_API_PORT ?? 8011);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5175);
const here = dirname(fileURLToPath(import.meta.url));
const backendDir = resolve(here, '..', 'backend');
const python =
  process.env.E2E_PYTHON ??
  (process.platform === 'win32'
    ? join(backendDir, '.venv', 'Scripts', 'python.exe')
    : join(backendDir, '.venv', 'bin', 'python'));
const database = join(tmpdir(), `dyscover-e2e-${Date.now()}.db`).replace(/\\/g, '/');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: backendDir,
      url: `http://127.0.0.1:${API_PORT}/api/health/ready`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        APP_ENV: 'test',
        DATABASE_URL: `sqlite:///${database}`,
        SECRET_KEY: 'e2e-secret-key-not-for-production-0123456789',
        RATE_LIMIT_ENABLED: 'false',
        CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
        LEXI_TEST_PROVIDER: 'echo',
        GROQ_API_KEY: '',
        // Synthetic research predictor, served from the committed artifact in backend/artifacts.
        RESEARCH_DEMO_ENABLED: 'true',
      },
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
