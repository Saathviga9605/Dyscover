# Implementation State

Last updated: 2026-10-20 (engineering pass in progress). This file replaces an
earlier version whose "verified" claims did not hold: at the start of this pass
the backend could not be imported (duplicate `practice_events` table) and most
data endpoints were unauthenticated. See `risk-register.md` for the defects found.

## Done and verified (commands + results recorded below)

### Persistence (Phase 2)
- `app/models.py` rebuilt: removed the corrupted duplicate `PracticeEvent`; added
  `RefreshToken`, `User.token_version`, `Conversation.title`, `Message.model`,
  role check constraint, chat indexes; `ON DELETE CASCADE` on all child-data FKs.
- Alembic is now authoritative. `1c08bf9c22ca` is a real baseline (runs only on
  empty DBs); `0002_auth_tokens_lexi` adds the new tables/columns, back-fills
  legacy SQLite columns and rebuilds FKs with cascade on PostgreSQL. Broken
  `20231020_lexi_chat` (dangling `down_revision`) removed.
- Startup: development auto-runs `upgrade head`; production refuses to start
  unless at head (`app/core/migrations.py`). `create_all` and ad-hoc `ALTER`s removed.
- SQLite connections enable `PRAGMA foreign_keys=ON`.
- Evidence: `tests/test_migrations.py` (fresh upgrade has **zero** autogenerate
  diffs; downgrade/upgrade; legacy DB upgrade keeps rows). A copy of the real
  dev DB (`dyscover.db`, 71 users / 5 700 trials) upgraded with identical row
  counts. The original `dyscover.db` was **not** modified.
- Known drift (documented, acceptable): legacy SQLite DBs keep FKs without
  cascade and a few nullable legacy columns; deletion is done in explicit order so
  behaviour is identical.

### Auth & security (Phase 3)
- Secret key: no insecure default; production refuses empty/placeholder/<32 chars,
  wildcard CORS, insecure SameSite=None.
- Access JWT (15 min, `ver` claim) + opaque rotating refresh token in HttpOnly
  cookie scoped to `/api/auth`, SHA-256 hashed in DB, reuse detection revokes
  the family. CSRF header required on cookie endpoints. Password change and
  `logout-all` invalidate all sessions. Timing-equalised login, no PII in audit logs.
- Rate limiting is real now (`SlowAPIMiddleware` + per-route limits).
- Central authorization in `app/access.py`; every child-data router (children,
  assessments, trials, events, gaze, speech, ML, personalization, remedial,
  privacy, chat) is owner-scoped; denials are 404. Educator access is granted by
  the parent by email (read-only summaries); educator self-authorization removed.
  `X-User-Id` header identity removed. `/api/ml/quality` is admin-only.
- Evidence: `tests/test_security.py` (88 tests incl. a parametrised check that
  every non-public route returns 401 anonymously), `tests/test_educator_access.py`.

### API (Phase 4)
- `main.py` reduced to app assembly; routers registered once under `/api`
  (broken duplicate `/api/v1/v1` aggregate removed). New routers:
  `app/children`, `app/assessments`, `app/educator`, `app/chat`.
- Server-side scoring for the 5 visual games (`app/assessments/scoring.py`);
  speech games marked `client_reported`. Idempotent trial/event/gaze writes;
  completed assessments reject new trials (409); summary totals counted server-side.
- Safe validation errors (no echoed input), generic 500 with request id, request
  size guard, validated `X-Request-ID`, liveness `/api/health` + readiness
  `/api/health/ready`.

### Privacy (Phase 13, backend)
- Export no longer leaks `password_hash`; includes conversations; deletion
  service deletes in dependency order (previously left orphans / failed on PG),
  requires password, removes conversations, refresh tokens, educator links.
- Evidence: `tests/test_privacy.py`.

### Lexi backend (Phase 11)
- `app/chat/service.py` (Groq SDK 0.37.1, sync client in threadpool),
  `app/chat/routes.py`. Honest errors (503 not configured, 429, 504, 502); no
  writes until the model answers; `client_message_id` idempotency; history
  bounded; contact details redacted; system prompt server-side only.
- Evidence: `tests/test_chat.py` (provider mocked at boundary). **Live Groq not
  verified: no `GROQ_API_KEY` on this machine** (`test_live_groq_request` skipped).

### Speech demo hardening (Phase 8, partial)
- Authenticated, streamed size limit, private temp file always deleted, provider
  chosen without mutating `os.environ`, threadpool + timeout + concurrency cap,
  cached providers, HF provider no longer claims AVAILABLE without deps.

## Test evidence (latest)
| Command (from `backend/`) | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q --ignore=tests/ml/speech` | 292 passed, 1 skipped (live Groq) |
| Frontend baseline before changes: `npx tsc -b`, `npx vitest run` | exit 0; 142 passed |

## Outstanding (in order)
1. Frontend: fix API base URL (`/api/api/...` bug), in-memory access token +
   refresh flow, `credentials: 'include'`, protected routes, child selection
   (stop auto-creating anonymous children), educator dashboard + parent sharing
   UI, account/privacy page, Lexi widget against real API, i18n of new strings,
   offline queue handling of 4xx, modality `null` coverage.
2. Frontend tests + Playwright journeys (8 games, auth, Lexi mocked at network).
3. ML pipeline audit run + `ai-ml-validation.md` rewrite with real numbers.
4. Speech ML tests (`tests/ml/speech`) — check transformers availability.
5. Docker/compose/nginx hardening; `.env.example`; requirements (alembic, groq, email-validator).
6. Docs: system-architecture, risk-register, final-integration-report,
   invention disclosure refresh, README.

## Next action
Frontend API client + auth rewrite (`frontend/src/services/apiClient.ts`,
`frontend/src/auth/AuthContext.tsx`).
