# System Architecture

Status as of 2026-10-21. Describes what the code does, not intended future features.

## Components

| Component | Technology | Location |
|---|---|---|
| Web client | React 19, TypeScript 6, Vite 8, React Router 7 | `frontend/src` |
| API | FastAPI 0.156 / Starlette 1.9, Python 3.13 | `backend/app` |
| Database | SQLAlchemy 2.0; PostgreSQL 16 (production), SQLite (development/tests) | `backend/app/models.py` |
| Migrations | Alembic (authoritative) | `backend/alembic/versions` |
| Lexi assistant | Groq Chat Completions via official `groq` SDK | `backend/app/chat` |
| Gaze | WebGazer 3.5.3 in the browser (pinned + SRI); only coordinates reach the API | `frontend/src/gaze`, `backend/app/gaze` |
| Speech (games) | Browser Web Speech API; only transcripts/features reach the API | `frontend/src/games/speech`, `backend/app/speech` |
| Speech (demo/research) | Optional local faster-whisper / Hugging Face Whisper | `backend/app/speech/provider.py`, `backend/app/ml/speech` |
| Research ML | scikit-learn baselines on synthetic data | `backend/app/ml` |
| Deployment | Docker Compose: postgres → migrate → backend → nginx(web) | `docker-compose.yml` |

## Request path

```
Browser ──/api──▶ Vite proxy (dev) or nginx (prod, CSP/HSTS-ready, 11 MB body cap)
        ──▶ FastAPI middleware: request-id, size guard, security headers, CORS, rate limit
        ──▶ auth dependency (Bearer JWT; token_version checked against DB)
        ──▶ app/access.py ownership check (child → owner, or granted educator, read-only)
        ──▶ router/service ──▶ SQLAlchemy session (one per request, rollback on error)
```

All routers are mounted once under `/api`. API docs (`/docs`, `/openapi.json`) are disabled when `APP_ENV=production`.

## Authentication and sessions

- Registration: parent or educator only (`admin` cannot self-register). Emails normalised to lowercase; bcrypt (12 rounds); passwords 8–72 bytes.
- Login returns a 15-minute access JWT (HS256, claims `sub`, `role`, `ver`, `type`, `iat`, `exp`, `jti`) and sets an HttpOnly refresh cookie (`dyscover_refresh`, path `/api/auth`, SameSite=Lax, Secure in production).
- Refresh tokens are opaque, stored as SHA-256 digests (`refresh_tokens`), rotated on every use; reusing a rotated token revokes the whole family.
- Cookie endpoints (`/refresh`, `/logout`) require `X-Requested-With: dyscover` (CSRF defence via CORS preflight).
- Password change and "log out everywhere" increment `users.token_version`, invalidating every access token immediately, and revoke all refresh tokens.
- The browser keeps the access token in memory only and restores the session from the cookie on reload.

## Authorization model

| Actor | Can |
|---|---|
| Parent (owner) | Full access to own child profiles and everything derived from them; grant/revoke educator access by educator email; export and delete own data. |
| Educator | Read aggregated learner summaries and personalization views for children whose owner granted access; relinquish access. Never raw trials/events/gaze/speech; cannot create children or self-grant. |
| Admin | Platform-wide data-quality report (`/api/ml/quality`). Created only in the database. |
| Anyone | Health/readiness, register/login, static status endpoints. |

Unauthorised access to an existing resource returns **404** (not 403) so IDs cannot be probed. `tests/test_security.py` enumerates every route from the OpenAPI schema and asserts anonymous requests are rejected.

## Data model (ownership chain)

```
users ─┬─ child_profiles ─┬─ assessment_sessions ─┬─ game_sessions ── trials ─┬─ interaction_events
       │                  │                       ├─ assessment_summaries    ├─ gaze_samples, fixations
       │                  │                       ├─ session_feature_vectors ├─ feature_vectors
       │                  │                       └─ speech_sessions ◀───────┘ (optional trial link)
       │                  ├─ practice_sessions ── practice_events   (remedial; never assessment evidence)
       │                  └─ educator_learner_assignments ──▶ users (educator)
       ├─ refresh_tokens
       └─ conversations ── messages (role ∈ {user, assistant}; system prompt never stored)
```

All child-data foreign keys declare `ON DELETE CASCADE` (enforced on PostgreSQL); deletion code also removes rows explicitly in dependency order so legacy SQLite databases behave identically (`app/privacy/service.py`). Timestamps are naive UTC.

## Assessment data integrity

- Trials for the five visual games are **scored on the server** (`app/assessments/scoring.py`, parity-tested against the TypeScript rules); client-claimed results are kept only as `metadata.client_reported`. Speech-game correctness is `client_reported`.
- Trials with neither a response nor a claimed outcome are stored **unscored**; speech trials whose recognition failed or heard no speech are stored unscored (not as wrong answers).
- Trial, event and gaze writes are idempotent (offline queue retries cannot duplicate); completed assessments reject new trials (409); summary totals are counted server-side.
- Limitation: stimuli are generated in the browser, so the server checks internal consistency, not that a stimulus was actually displayed.

## Personalization and remedial practice

Deterministic, rule-based (`app/personalization`, `app/remedial`). Uses only scored trials of the five visual games (domains: visual-symbol discrimination, orthographic recognition, working memory, attention/visual search). Speech games are not yet modelled by personalization. Output is labelled as suggestions, with reasons, and never uses clinical categories; practice data is stored separately from assessment data.

## Lexi

`POST /api/chat/conversations/{id}/messages` → build prompt (server-side system prompt + up to 20 recent turns, ≤12 000 characters, contact details redacted) → Groq (timeout 30 s, 1 retry) → only then persist both messages in one transaction. Failures map to 503 (not configured), 429, 504, 502 with no stored message. `client_message_id` makes retries idempotent. Tests replace the provider at the boundary (`set_provider`); the browser e2e suite uses an echo provider that can only be enabled with `APP_ENV=test`.

## Startup and operations

- Development: `uvicorn app.main:app` runs `alembic upgrade head` automatically (SQLite by default).
- Production: `APP_ENV=production` requires a ≥32-character `SECRET_KEY`, rejects wildcard CORS, and refuses to start unless the schema is already at head; Compose runs a one-shot `migrate` service first.
- `/api/health` = liveness; `/api/health/ready` = database reachable + schema revision + Lexi configuration state.
- Logs: request id on every response; audit events are JSON with opaque IDs and reason codes only (no emails, tokens or child names); unhandled errors return a generic 500 with the request id.
