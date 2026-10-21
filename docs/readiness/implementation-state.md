# Implementation State

Last updated: 2026-10-21. Most changes are in commit `a45d6b0`; the remainder (ML validation, docs, Lexi race fix) is uncommitted in the working tree.

Start of this pass (2026-10-20): the backend could not be imported; most data endpoints were unauthenticated; login could not work from the frontend; Lexi was hard-coded. Earlier "verified" claims were inaccurate; old reports are archived in `archive/`.

## Completed (with evidence in `final-integration-report.md`)

1. Persistence: models rebuilt, authoritative Alembic chain (`1c08bf9c22ca` baseline, `0002_auth_tokens_lexi`), cascade FKs, migration-based startup, isolated test DBs, PostgreSQL test run.
2. Security: fail-safe config, rotating DB-backed refresh tokens, token versioning, CSRF header, real rate limiting, central ownership checks on every router, owner-granted educator access, admin-only platform report, safe errors, request-size guard, PyJWT, patched FastAPI/Starlette/python-multipart.
3. API: routers split (`children`, `assessments`, `educator`, `chat`, `privacy`), server-side scoring, idempotent writes, state transitions, pagination, liveness/readiness.
4. Frontend: same-origin API client with memory-only token and refresh, route guards, child selection, parent dashboard (children, sharing, observations), educator dashboard, account/privacy page, Lexi widget + logo, accessibility fixes (contrast token, skip link, focus, reduced motion, labels), Tamil/English catalogs with coverage test, pinned dependencies, lint config fixed.
5. Games: fixed double submit, pause traps, Word Maze completion, speech consent bypass and disabled consent button, recognition failures stored unscored, duplicate assessment creation, aborted-recognition race.
6. ML: missingness indicators, artifact path check, multi-seed experiment with permutation probe (`app/ml/synthetic/experiment.py`), validation report rewritten.
7. Speech: demo hardened; speech-ML tests pass on Windows (xfail removed).
8. Gaze: WebGazer pinned with SRI; loader double-injection fixed.
9. Lexi: Groq service, persistence, honest errors, redaction, idempotency, e2e with echo provider; history-load race fixed (found by the final e2e run).
10. Deployment: Dockerfiles (non-root, health checks), Compose with migrate step and internal API, nginx with CSP/Permissions-Policy, env examples, split requirements; verified locally on PostgreSQL.
11. Docs: `system-architecture.md`, `risk-register.md`, `ai-ml-validation.md`, `final-integration-report.md`, `invention-disclosure-draft.md`, `docs/privacy.md`, README sections.

## Blocked (external prerequisites)

- Live Groq verification — needs `GROQ_API_KEY` (`LIVE_GROQ=1 LIVE_GROQ_API_KEY=… pytest tests/test_chat.py -k live`).
- Speech fine-tuning experiment — needs a licensed children's read-speech dataset with speaker IDs.
- Physical camera/microphone verification — needs a person with a device (manual test plan: grant consent, calibrate, play Letter Detective, check modality summary shows gaze samples; play a speech game in Chrome).
- Legal/compliance, clinical/specialist, native Tamil, penetration-test and accessibility (screen reader) reviews.

## Outstanding engineering items (not blocking)

- Code-split the frontend bundle (>500 kB main chunk).
- Shared rate-limit store for multiple API replicas.
- Server-side consent records; email verification; personalization for speech games.
- Speech-ML stack upgrade to transformers 5.x (risk B13).
- 52 lint warnings (style-level).

## Next action

Maintainers: review the diff, commit, and run the blocked verifications above. If resuming engineering work, start with bundle code-splitting, then the transformers 5.x migration.

## Screening pipeline (2026-10-21)

Implemented end to end (training → registry/eligibility gate → `GET /api/screening/children/{id}` → parent card). No model is installed or eligible, so the API returns `no_eligible_model` and no percentage is shown. See `ai-ml-validation.md` §8.

## Synthetic research predictor (2026-10-21)

- **Working:** a trained, committed artifact (`backend/artifacts/screening-synthetic/dyscover-research-synthetic`) scores real stored visual-run assessments through `POST /api/screening/research/children/{id}/assessments/{aid}/predict`. Results are stored in `research_predictions` (migration `0004`), and the page `/research/predictor` (EN/TA) shows them.
- **Scope:**
  - Off by default (`RESEARCH_DEMO_ENABLED`) and refused in production.
  - Only the owner or a granted educator can use it.
  - The output is never shown on the parent screening card.
- **Not covered:** speech-only assessments and Tamil assessments return explicit statuses instead of scores.
- See `ai-ml-validation.md` §9.

## Release state (2026-10-21)

Engineering release of the research/educational demo is complete and verified (see `final-integration-report.md` §8 and `project-completion-checklist.md`):
- PostgreSQL 16 validated: full suite, upgrade with data, rollback, backup and restore.
- Clean, isolated Python environment.
- Production Compose stack smoke-tested.
- Deployment guide in `docs/deployment.md`.

Remaining items are external: hosting/TLS, monitoring, legal review, real-device microphone/camera, clinical data.
