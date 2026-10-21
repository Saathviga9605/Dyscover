# Final Integration Report

Date: 2026-10-21. Environment: Windows 11, Python 3.13.14 (`backend/.venv`), Node 24, Chromium (Playwright 1.64.1), Docker 29.8.0. Replaces the previous report, whose "verified" claims did not hold (see `risk-register.md` Part A).

Classification: **Verified** = behaviour exercised by the tests/commands below. **Implemented, not fully verified** = code exists, evidence incomplete. **Blocked** = external prerequisite missing. **Not implemented** = absent.

## 1. Commands and results (final code)

| # | Command (directory) | Result |
|---|---|---|
| 1 | `pytest` (`backend`, temp SQLite, incl. speech-ML) | **380 passed, 1 skipped** (skipped = live Groq test, no key), exit 0 |
| 2 | `TEST_DATABASE_URL=postgresql+psycopg://… pytest --ignore=tests/ml/speech` against `postgres:16-alpine` | **293 passed, 1 skipped**, exit 0 |
| 3 | `pytest tests/test_migrations.py` | fresh upgrade has **0** autogenerate differences from the models; downgrade/upgrade and legacy-DB upgrade pass |
| 4 | Upgrade of a **copy** of the real `dyscover.db` (71 users, 3 443 children, 5 700 trials) | succeeded; identical row counts; original file untouched |
| 5 | `pip-audit -r requirements.txt` | No known vulnerabilities (optional speech-ML set: see risk B13) |
| 6 | `npx tsc -b --noEmit` (`frontend`) | exit 0 |
| 7 | `npx eslint .` | exit 0 — 0 errors, 52 warnings (mostly promise-handling style in tests/handlers) |
| 8 | `npx prettier --check src e2e` | clean |
| 9 | `npx vitest run` | **146 passed** (18 files), incl. translation-coverage test (every `t('…')` key exists in English and Tamil) |
| 10 | `npm run build` | exit 0 (warning: main chunk > 500 kB; code-splitting not yet done) |
| 11 | `npm audit --omit=dev` | 0 vulnerabilities |
| 12 | `npx playwright test` (real backend + temp DB + Vite; Lexi echo provider; speech-recognition API stubbed in the browser) | **16 passed** (desktop Chromium + Pixel 7 project), exit 0, on the final code |
| 13 | `docker compose build && up --wait` (postgres → migrate → backend → web) + scripted smoke test through nginx | all services healthy; migrations applied on PostgreSQL; register/login/refresh(CSRF)/child/assessment/server re-scoring/anonymous 401/export/account deletion/token revoked all as expected; API docs 404 in production; container runs as uid 10001 |
| 14 | `python -m app.ml.synthetic.experiment --seeds 1 2 3 4 5 --subjects 60` | see `ai-ml-validation.md`; evidence JSON in `evidence/` |
| 15 | WebGazer SRI check in Chromium | pinned 3.5.3 with correct hash loads; wrong hash blocked |

## 2. Explicit statements

- **Real Groq request: NOT executed.** No `GROQ_API_KEY` exists on this machine. Lexi is verified with the provider mocked at its boundary (pytest) and with an echo provider in the browser. `tests/test_chat.py::test_live_groq_request` is ready (`LIVE_GROQ=1 LIVE_GROQ_API_KEY=…`).
- **Speech fine-tuning experiment: NOT executed.** No licensed children's read-speech corpus with speaker IDs, and no Whisper weights, are available. No WER/CER is claimed.
- **Physical camera (gaze) test: NOT executed.** Gaze was exercised only through unit tests with mocks and API ingestion tests; no real webcam calibration was performed.
- **Real microphone: NOT executed.** Browser e2e tests replace the Web Speech API with a stub that "hears" the on-screen prompt.
- **Production deployment, TLS, backups, monitoring, restore: NOT verified.** Only a local Compose deployment was run.

## 3. Feature status

| Feature | Status | Evidence / notes |
|---|---|---|
| App starts via documented process (dev and Compose) | Verified | rows 1, 13 |
| Models ↔ migrations consistent; fresh + legacy upgrade | Verified | rows 3, 4 |
| Registration, login, refresh rotation/reuse detection, logout, logout-all, password change | Verified | `test_security.py`, e2e `auth.spec.ts` |
| Every protected route rejects anonymous calls; cross-user (IDOR) access blocked | Verified | `test_security.py` (OpenAPI-enumerated), e2e privacy spec |
| Roles: parent / educator (granted, read-only) / admin | Verified | `test_educator_access.py`, e2e sharing journey |
| Fail-safe production config (secret, CORS, cookies) | Verified | `test_security.py` config tests, row 13 |
| Rate limiting | Verified (login) | `test_login_is_rate_limited`; per-process only (risk B8) |
| Frontend ↔ backend contracts | Verified for exercised journeys | e2e suite; gaze status/batch types aligned |
| Five visual games (Letter Detective, Mirror Match, Word Flash, Sequence Quest, Word Maze) | Verified | e2e full run: 22 trials stored, server-scored, domains correct, assessment completed |
| Three speech games (Sound Quest Adventure, Letter Bubble Pop, Maze Runner Rush) | Verified with stubbed recognition; real ASR not verified | e2e: consent gate enforced, every trial has a speech session with features |
| Server-side scoring, idempotent writes, state transitions | Verified | `test_assessment_integrity.py` |
| Offline queue (drop permanent failures, single flush) | Implemented, not fully verified | unit tests; no browser offline test |
| Gaze capture | Implemented, not fully verified | API/unit tests; no real camera (row 2) |
| Personalization & remedial practice | Verified (rules, isolation, authorization); speech games not modelled | `test_personalization.py`, `test_remedial*.py` |
| ML feature extraction, synthetic training/evaluation, artifact integrity | Verified | rows 1, 14 |
| Real-world predictive inference | Not implemented (deliberately disabled) | `ai-ml-validation.md` §5 |
| Speech-ML pipeline code | Verified by tests; experiment Blocked | row 1; §2 |
| Lexi (persistence, context, ownership, errors, idempotency, UI) | Verified with mocked provider; live Groq Blocked | `test_chat.py`, e2e Lexi |
| English/Tamil switching, catalog coverage, honest unavailability | Verified (Tamil copy needs native review) | e2e language test, coverage test |
| Accessibility | Partially verified | axe (WCAG 2.1 A/AA rules) clean on parent dashboard, Lexi panel, account page; keyboard Escape/focus return; no manual screen-reader audit |
| Privacy export / child deletion / account deletion | Verified (SQLite + PostgreSQL) | `test_privacy.py`, e2e privacy, row 13 |
| Docker images, non-root, health checks, migration step | Verified locally | row 13 |
| Mobile layout | Verified for dashboard + Lexi at Pixel 7 size | e2e `@mobile` |

## 4. Diff review (final)

- No secrets committed (`.env` ignored; examples contain empty values only). Development key is clearly named and refused in production.
- Removed: broken migration, duplicate `app/audit.py`, broken `/api/v1` aggregate, unused Groq service stub, six debug scripts, committed coverage/test reports/build info.
- Test-only code paths: echo Lexi provider (requires `APP_ENV=test`), `TEST_DATABASE_URL`; nothing mocked in production paths.
- No tests were deleted or weakened to pass. Tests that encoded insecure behaviour were rewritten to assert the secure behaviour (header-based educator identity, anonymous child creation, fabricated trial outcomes, platform-wide quality report for parents). The `xfail` on two Windows audio tests was removed because they now pass.
- Most of this pass was committed by the maintainer as `a45d6b0` (2026-10-21). Later changes (ML validation run and fixes, Lexi race fix, documentation, test-marker cleanup) are in the working tree, uncommitted.

## 5. Final e2e re-run

The penultimate full run found a real race (Lexi duplicated the first reply when a new conversation's history load overlapped the first send). After the fix the Lexi journey passed in two consecutive isolated runs, and the final full suite passed 16/16 (3.8 min).

## 6. Reading-difficulty screening pipeline (2026-10-21)

- Added: `app/ml/screening/` (schema, training, model, registry + eligibility gate, service, routes), `ScreeningResult` table (migration `0003`), privacy export/deletion coverage, parent `ScreeningCard` (EN/TA). Details: `ai-ml-validation.md` §8.
- Results: backend `pytest` → **403 passed, 1 skipped**; frontend typecheck 0 errors, lint 0 errors, vitest 151 passed, build OK; Playwright 16 passed. The visual run asserts the card shows `no_eligible_model` and no percentage. Fixed a race in `extract_profile` that this run found (concurrent dashboard requests hit a UNIQUE constraint); the fix is guarded by `test_concurrent_feature_extraction_does_not_fail`.
- **No eligible model exists.** No labelled real-child data, external validation, specialist review or ethics approval. Real-child risk estimates: **NO-GO**.

## 7. Synthetic research predictor (2026-10-21)

- **Model:** trained and saved at `backend/artifacts/screening-synthetic/dyscover-research-synthetic/`. It is gradient boosting (depth 3), sigmoid-calibrated, v1.0.0, SHA-256 `16d52b48…f157d`. Retraining with seed 42 reproduces the same hash.
- **Data:** an assessment-level synthetic dataset (1,600 assessments, 800 participants) that mirrors the app's visual run.
- **Synthetic test results (160 held-out participants):** ROC-AUC 0.992, against 0.500 for the baseline. This reflects recovery of simulator settings, not children (`ai-ml-validation.md` §9).
- **Real flow verified:** a child plays the five visual games in the browser; 22 trials are stored; feature extraction runs; the research API (`POST /api/screening/research/children/{id}/assessments/{aid}/predict`) scores them with the saved model; the result is stored in `research_predictions`; and `/research/predictor` displays exactly the returned percentage, labelled "Synthetic research score … NOT a real-child dyslexia probability" (Playwright).
- **Separation verified:** the parent card still shows `no_eligible_model` and no percentage.
- **Results:**
  - Backend `pytest`: **431 passed, 1 skipped**. The skip is the live Groq test, which needs `LIVE_GROQ=1`.
  - Frontend: typecheck 0 errors, lint 0 errors (52 warnings, all in pre-existing files), Vitest **160 passed**, production build OK.
  - Playwright: **19 passed** (4.8 min), with no IntegrityError or traceback in the server log.
- **Test isolation fix:** `tests/conftest.py` now pins `RESEARCH_DEMO_ENABLED=false` and an empty `SCREENING_MODEL_DIR`. Previously the suite inherited these from a developer's `backend/.env`.
- **Not verified here:** migration `0004` on PostgreSQL. No PostgreSQL server is available in this environment; on SQLite it passes the zero-diff migration test.
