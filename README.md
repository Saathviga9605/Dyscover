# Dyscover

> **A gamified, AI-assisted early reading-difficulty screening and support platform for children aged 4–10.**
> Children play eight short games; Dyscover records what they actually do, turns it into honest observations for parents and educators, and suggests practice. A friendly assistant, Lexi, answers adults' questions.
>
> **Dyscover is not a diagnostic or clinical system.** No model validated on real children is included, and the parent experience never shows a clinical probability.

**Version 0.2.0 · Research/educational demo · Engineering release verified 2026-10-21** ([release record](docs/readiness/final-integration-report.md))

---

## Table of Contents

- [At a Glance](#at-a-glance)
- [What Dyscover Does](#what-dyscover-does)
- [The Eight Games](#the-eight-games)
- [For Parents and Educators](#for-parents-and-educators)
- [Lexi, the Assistant](#lexi-the-assistant)
- [Screening and Machine Learning](#screening-and-machine-learning)
- [Speech and Eye Tracking](#speech-and-eye-tracking)
- [Architecture](#architecture)
- [Security](#security)
- [Privacy and Ethics](#privacy-and-ethics)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Overview](#api-overview)
- [Testing and Verified Results](#testing-and-verified-results)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Known Limitations and Remaining Work](#known-limitations-and-remaining-work)
- [Roadmap](#roadmap)
- [License and Attributions](#license-and-attributions)

---

## At a Glance

| Area | What is in the repository |
|---|---|
| Child experience | 8 games (5 visual, 3 speech), child explorer space, practice activities, mascot, accessibility panel |
| Adults | Parent dashboard, educator dashboard, controlled sharing by email, account page with export and deletion |
| Assistant | **Lexi**, powered by Groq (`openai/gpt-oss-120b`), with saved conversations and safety prompting |
| Languages | English and Tamil interface (Tamil game content only where it is language-neutral) |
| Screening | A 15-feature screening schema, a strict model eligibility gate, and an honest parent screening card |
| ML research | A trained **synthetic research predictor** on its own research page, clearly labelled as not a dyslexia probability |
| Backend | FastAPI, SQLAlchemy 2, Alembic migrations, PostgreSQL or SQLite, JWT with rotating refresh cookies, rate limiting, structured audit logging |
| Frontend | React 19, TypeScript 6, Vite 8, React Router 7 |
| Quality | 431 backend tests, 160 Vitest tests, 19 Playwright browser journeys with axe accessibility checks |
| Deployment | Docker Compose (PostgreSQL, one-shot migrations, API, unprivileged nginx), [deployment guide](docs/deployment.md) |

## What Dyscover Does

- Runs short, playful activities that exercise skills related to early reading.
- Stores every trial on the server, which **re-scores visual answers itself**, so a modified client cannot fake results.
- Extracts behavioural features (accuracy, timing, hesitation, per-domain accuracy, optional speech and gaze) with explicit availability metadata. **Missing data stays missing and is never turned into 0.**
- Shows parents and educators **observations**: relative strengths, areas where practice may help, progress over time, and suggested next steps.
- Adapts game difficulty and recommends practice activities with transparent, rule-based personalization.
- Keeps a separate, clearly labelled **research** path for machine-learning experiments.

**What it does not do**

- Diagnose dyslexia, ADHD or any other condition.
- Show parents a "dyslexia probability". The parent card only shows a percentage from a model that has passed real validation, and no such model exists.
- Store raw camera video or microphone audio.
- Use a child's identity as a model input.

## The Eight Games

| Game | Skill area (domain code) | Modality | Trials per run |
|---|---|---|---|
| Letter Detective | Visual symbol discrimination (`visual-symbol-discrimination`) | Visual | 5 |
| Mirror Match | Visual symbol discrimination | Visual (language-neutral; also in Tamil) | 5 |
| Word Flash | Orthographic recognition (`orthographic-recognition`) | Visual | 5 |
| Sequence Quest | Working memory (`working-memory`) | Visual | 4 |
| Word Maze | Attention / visual search (`attention-visual-search`) | Visual | 3 |
| Sound Quest Adventure | Phonological awareness (`phonological-awareness`) | Speech | 3+ |
| Letter Bubble Pop | Phonological awareness | Speech | 3+ |
| Maze Runner Rush | Rapid naming (`rapid-naming`) | Speech | 3+ |

**The visual adventure:**
- The five visual games run together as one assessment (22 trials).
- It supports pause and resume.
- Double taps can't submit an answer twice.
- Word Maze can be finished early.

**The speech adventure:**
- It is blocked until an adult consents to microphone use.
- When speech recognition fails or hears silence, the trial is stored as **unscored**. It never counts as a wrong reading answer.

## For Parents and Educators

**Parent dashboard:**
- Child profiles.
- "What we observed" by skill area.
- The dyslexia-risk screening card (see [below](#screening-and-machine-learning)).
- Modality summary: was speech or eye tracking recorded?
- Practice suggestions and a progress history.

**Educator dashboard:**
- Read-only summaries of learners a parent has explicitly shared, by the educator's account email.
- Parents can revoke access; educators can leave.
- Raw traces stay owner-only.

**Practice:**
- Remedial activities with sessions, events and progress tracking (`/api/remedial/*`).
- Recommended from the child's observed profile.

**Account page:**
- Change password, sign out of all sessions.
- See a data summary, download a full export (ZIP), delete the account.

## Lexi, the Assistant

- Lexi is a chat assistant for **adults**. It explains the games, the observations and general reading support in short, non-diagnostic answers.
- **Provider:** Groq (`GROQ_API_KEY`, default model `openai/gpt-oss-120b`). Without a key, Lexi says it is not configured; the rest of the app keeps working.
- **Saved conversations:** previous turns are sent as context. Each user sees only their own history.
- **Safety:**
  - a strict system prompt with no diagnosis and short replies;
  - no child data is sent to Groq;
  - rate limited;
  - the app tells users that messages go to Groq.
- **Verified:** a live Groq request test passed with a configured key. The browser tests use a test-only echo provider, which is refused outside `APP_ENV=test`.

## Screening and Machine Learning

Dyscover separates **what can honestly be shown to families** from **research experiments**.

### 1. Parent screening card (clinical path, honest by design)

- `GET /api/screening/children/{id}` always returns the observation summary: answered and unscored activities, strengths, support areas, limitations and next steps.
- A percentage appears **only** if an installed model passes every check in the eligibility gate:
  - trained on real labelled data (recorded in both the model card *and* the artifact);
  - calibrated probability output;
  - a reliable held-out sample;
  - external validation, specialist review and ethics approval recorded;
  - a defined age and language population;
  - an intact SHA-256 checksum and matching runtime.
- **Today no model passes**, so the card shows "No validated screening model yet". Risk bands appear only from specialist-approved thresholds; none are invented.
- **Target definition:** `elevated_reading_difficulty_risk_v1`, i.e. "a standardised reading assessment, administered independently, recommended further assessment or support". It is deliberately *not* "has dyslexia".

### 2. Synthetic research predictor (research path)

A real, trained, saved model that runs on a child's **real stored game results**:

| | |
|---|---|
| Artifact | `backend/artifacts/screening-synthetic/dyscover-research-synthetic/` (`model.pkl` + `model_card.json`) |
| Model | Gradient boosting (depth 3), sigmoid-calibrated, v1.0.0, SHA-256 `16d52b48fa9765f36dabd8bf3bf28da20a4220630885a594b208a6ef732f157d` |
| Training data | 1,600 synthetic assessments from 800 simulated participants. Each one mirrors the real visual run: 5 games, 22 trials, 4 domains |
| Label | 1 when the simulator generated the participant from one of four "difficulty" profiles. It is a **simulator setting, not a clinical label** |
| Selection | Highest **validation** ROC-AUC among logistic regression, random forest and gradient boosting, compared with a baseline that always predicts the average |
| Held-out synthetic test | ROC-AUC 0.992 (95% CI 0.984–0.998) on 160 participants; baseline 0.500 |
| Reproducible | Retraining with seed 42 produces the identical SHA-256 |

**What the score means:** the probability of the *synthetic* target under this model. **It is not a real-child dyslexia probability.**

The high metrics are expected and say nothing about children, because the label and the features come from the same simulator parameters.

How the separation is enforced:

- **Separate page:** `/research/predictor` (English and Tamil). It has child and session pickers, the labelled score, and a feature table showing how much each value moves the model's own score. Values outside the synthetic training range are flagged.
- **Off by default:** `RESEARCH_DEMO_ENABLED=false`. The server **refuses to start** in production if it is turned on, and the production image does not contain the artifact.
- **Access:** only the child's parent or a granted educator; anyone else gets 404.
- **Storage:** results are stored once per assessment and model version in their own table, `research_predictions`. They are never written to screening results, and they are included in export and deletion.
- **No crossover:** a synthetic model can never pass the production gate, even if its card is edited or the production directory points at it. The parent card never falls back to it.
- **Explicit statuses** instead of guesses: `insufficient_observations` (for example a speech-only run), `unsupported_population` (Tamil, or age outside 4–10), `assessment_incomplete`, `no_research_model`, `model_version_conflict`.

Full method, label rules, every metric and limitations: [`docs/readiness/ai-ml-validation.md` §9](docs/readiness/ai-ml-validation.md).

### 3. Research ML subsystem

`backend/app/ml/` also contains:
- the 40-feature extraction registry;
- the session-level synthetic simulator (9 profiles, seeded and checksummed);
- subject-level splits and baseline experiments;
- data-quality reports (admin only).

The older `POST /api/ml/predict/session/{id}` always returns `unavailable`.

```bash
cd backend
# Train, evaluate and save the synthetic research predictor (~15 s)
python -m app.ml.screening.training --synthetic-demo --version 1.0.0 --output artifacts/screening-synthetic/dyscover-research-synthetic
# Verify artifacts in a fresh process: checksum, runtime, which registry may serve them
python -m app.ml.screening.verify
# Train a real screening model (requires a provenance file; see ai-ml-validation.md §8.5)
python -m app.ml.screening.training --data dataset.csv --provenance provenance.json --output models/screening/<id>
# Session-level synthetic data and experiments
python -m app.ml.synthetic.cli generate --help
python -m app.ml.synthetic.experiment --seeds 1 2 3 4 5 --subjects 60
```

**To use the research predictor locally:**
1. Set `RESEARCH_DEMO_ENABLED=true` in `backend/.env` (development only) and restart the backend.
2. Play the visual adventure for a child.
3. Choose **Open the synthetic research predictor** on the parent dashboard.

## Speech and Eye Tracking

**In-game speech:**
- Uses the browser's Web Speech API, only after adult consent.
- No audio is stored; only transcripts and alignment features are kept.
- Accuracy for children and for Tamil has **not** been measured.

**Speech ML tooling** (`backend/app/ml/speech/`, optional `requirements-speech-ml.txt`):
- Whisper fine-tuning and evaluation: manifests, speaker-aware splits, WER/CER, experiment registry and CLI.
- An optional local Whisper provider for the `/api/speech/demo/*` endpoints.
- No fine-tuning run has been done: there is no licensed corpus of children's read speech. Guide: [`docs/speech-ml-pipeline.md`](docs/speech-ml-pipeline.md).

```bash
python -m app.ml.speech.cli validate --manifest data/manifest.jsonl --base-dir data/
python -m app.ml.speech.cli split --manifest data/manifest.jsonl --output-dir data/splits --seed 42 --speaker-aware
python -m app.ml.speech.cli train --model openai/whisper-tiny --train-manifest data/splits/manifest_train.jsonl --val-manifest data/splits/manifest_validation.jsonl --output-dir outputs/whisper-smoke --epochs 1 --max-steps 10
python -m app.ml.speech.cli evaluate --model outputs/whisper-smoke --test-manifest data/splits/manifest_test.jsonl
```

**Eye tracking (optional):**
- WebGazer 3.5.3, pinned and integrity-checked (SRI), loaded only after consent.
- Only gaze coordinates are sent, never video.
- If it is unavailable, the app continues without it and gaze features stay missing.

## Architecture

```
Browser (React SPA)                         nginx (unprivileged)              FastAPI (uvicorn, non-root)          PostgreSQL 16
─────────────────────────                   ───────────────────               ─────────────────────────────        ─────────────
Child space · 8 games · practice   ──────▶  serves SPA, CSP & security  ───▶  auth · children · assessments  ───▶  Alembic-managed
Parent / educator dashboards                headers, proxies /api             educator · personalization            schema (0001→0004)
Screening card · research page                                                remedial · gaze · speech · privacy
Lexi widget · EN/TA · a11y panel                                              screening + research ML · Lexi ──▶ Groq (optional)
```

### Data model

```
User ──┬── ChildProfile ──┬── AssessmentSession ──┬── GameSession ── Trial ──┬── InteractionEvent
       │                  │                       │                         └── GazeSample (optional)
       │                  │                       ├── SpeechSession (optional)
       │                  │                       ├── SessionFeatureVector
       │                  │                       ├── ScreeningResult      (eligible clinical models only)
       │                  │                       ├── AssessmentSummary
       │                  │                       └── ResearchPrediction   (synthetic research models only)
       │                  ├── EducatorLearnerAssignment (sharing)
       │                  └── PracticeSession ── PracticeEvent
       ├── RefreshToken (hashed, rotating)
       └── Conversation ── Message (Lexi)
```

### Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, React Router 7, Vitest 5, Testing Library, Playwright 1.64 + axe |
| Backend | Python 3.13, FastAPI 0.156, Starlette 1.9, SQLAlchemy 2.0, Pydantic 2, Alembic, PyJWT, slowapi, Groq SDK |
| Database | PostgreSQL 16 (production, verified), SQLite (development and tests) |
| ML | scikit-learn 1.6.1, NumPy 2.2.2; optional PyTorch, Transformers, jiwer, librosa for speech ML |
| Deployment | Docker Compose, `python:3.13-slim`, `nginx-unprivileged` |

## Security

- **Authentication:**
  - Short-lived JWT access tokens are kept in memory only, never in `localStorage`.
  - Refresh tokens are rotating, hashed in the database, HttpOnly cookies with reuse detection.
  - Changing the password ends every other session; "log out everywhere" is available.
- **Authorization:**
  - Central ownership checks on every child-related route (`app/access.py`).
  - Educators get read-only access, and only after the owner grants it.
  - A denied request returns **404**, so IDs reveal nothing about existence.
- **Integrity:** visual answers are re-scored on the server, and anomalies are recorded.
- **Hardening:**
  - Rate limits on auth, chat, export and uploads; CSRF header on cookie endpoints; exact-origin CORS.
  - Request-size limits; security headers (CSP, frame denial, nosniff, referrer policy).
  - Production startup refuses empty, placeholder or short `SECRET_KEY`s, `*` CORS, and research mode.
- **Logs:** request IDs only, with no tokens, passwords or feature values. Security-relevant actions go to a structured audit log that uses opaque IDs only. Screening logs hold only status and IDs.
- **Dependencies:** `pip-audit` and `npm audit` report no known vulnerabilities (2026-10-21).

There has been no independent penetration test, and the project holds no security certification.

## Privacy and Ethics

See [`docs/privacy.md`](docs/privacy.md).

- **Not a diagnosis.** Observations are descriptive, and the copy avoids diagnostic language. This is checked in browser tests.
- **Missing is not zero.** Unrecorded speech or gaze stays unavailable, and failed recognition is never a reading error.
- **Consent-gated capture.** The microphone and camera are used only after an adult opts in. No audio or video is stored.
- **Owner-only access**, plus read-only summaries for educators the parent chooses.
- **External services:**
  - Lexi messages go to Groq.
  - Browser speech recognition may send audio to the browser vendor.
  - Both are disclosed in the app.
- **Export and erasure:** the ZIP export uses an explicit field allow-list and never includes credentials. Account and child deletion remove all related records; this was verified on PostgreSQL.
- Compliance with COPPA, GDPR, the UK Children's Code or India's DPDP Act has **not** been assessed ([risk register](docs/readiness/risk-register.md)).

## Quick Start

### Prerequisites

- Python 3.13 and Node.js 22+.
- Optional: Docker (for PostgreSQL and the production stack) and a Groq API key (for Lexi).

### Backend (development, SQLite)

Windows PowerShell (verified with Python 3.13.14):

```powershell
cd backend
python -m venv .venv                       # isolated: .venv\pyvenv.cfg must say include-system-site-packages = false
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
# optional: python -m pip install -r requirements-speech-ml.txt   (offline speech-ML tooling and its tests)
# optional: create backend\.env with GROQ_API_KEY=..., GROQ_MODEL=..., RESEARCH_DEMO_ENABLED=true (dev only)
python -m uvicorn app.main:app --reload    # applies Alembic migrations automatically in development
```

On macOS/Linux, use the same steps with `source .venv/bin/activate`. A venv created with `--system-site-packages` silently imports global or user packages; recreate it as above.

API docs are at http://localhost:8000/docs (disabled when `APP_ENV=production`).

### Frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173 ; /api is proxied to :8000
```

**First run:**
1. Register a parent account and add a child.
2. Play **Play the visual adventures** (and the speech adventure, if you like).
3. Return to the dashboard to see observations, the screening card and suggestions.

Educators register separately; a parent shares a child by the educator's account email.

### Production-style stack (Docker Compose)

```bash
cp .env.example .env              # set POSTGRES_PASSWORD, SECRET_KEY (>= 32 random chars), PUBLIC_ORIGIN
docker compose up -d --build --wait   # postgres -> migrate (alembic upgrade head) -> backend (ready) -> web
# open http://localhost:8080  — put TLS in front of "web" for any real deployment (docs/deployment.md)
```

## Configuration

Backend settings come from environment variables or `backend/.env` (never committed):

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` or `production` |
| `SECRET_KEY` | dev-only key | **Required in production**: ≥ 32 random characters |
| `DATABASE_URL` | `sqlite:///./dyscover.db` | PostgreSQL: `postgresql+psycopg://user:pass@host:5432/db` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated exact origins; `*` refused in production |
| `AUTO_MIGRATE` | on outside production | Production runs `alembic upgrade head` as an explicit step and refuses an outdated schema |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | 15 / 7 | Session lifetimes |
| `REFRESH_COOKIE_SECURE` / `REFRESH_COOKIE_SAMESITE` | secure in production / `lax` | |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CHAT` | on, `10/minute`, `20/minute` | |
| `GROQ_API_KEY`, `GROQ_MODEL` | empty, `openai/gpt-oss-120b` | Without a key, Lexi reports "not configured" |
| `DYSCOVER_ASR_PROVIDER` (+ model vars) | unset | Optional local Whisper for the speech demo |
| `SCREENING_MODEL_DIR` | `models/screening` | Clinical screening models; only models passing every eligibility check are used |
| `RESEARCH_DEMO_ENABLED`, `RESEARCH_DEMO_MODEL_DIR` | `false`, `artifacts/screening-synthetic` | Synthetic research predictor; refused when `APP_ENV=production` |

The Compose stack reads `POSTGRES_PASSWORD`, `SECRET_KEY`, `PUBLIC_ORIGIN`, `WEB_PORT`, `REFRESH_COOKIE_SECURE`, `GROQ_API_KEY` and `GROQ_MODEL` from the root `.env` (see [`.env.example`](.env.example)).

Frontend: `VITE_API_URL` (default `/api`, same-origin) and `VITE_PROXY_TARGET` (dev proxy, default `http://localhost:8000`).

## API Overview

All endpoints are under `/api`; the live schema is at `/docs` in development. Everything except health, registration, login, refresh and logout requires `Authorization: Bearer <access token>`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`*, `/auth/logout`*, `/auth/logout-all`, `/auth/change-password`; `GET /auth/me` (*cookie + `X-Requested-With: dyscover`) |
| Children and sharing | `GET/POST /children`, `GET/PATCH/DELETE /children/{id}`, `GET/POST /children/{id}/educators`, `DELETE /children/{id}/educators/{educator_id}` |
| Assessments | `POST /assessments`, `GET /assessments/{id}`, `GET /children/{id}/assessments`, `POST /assessments/{id}/games/{game_id}/trials`, `POST\|GET /trials/{id}/events`, `POST /assessments/{id}/summary`, `GET /assessments/{id}/modality-summary` |
| Educator | `GET /educator/learners`, `GET /educator/learners/{id}/summary`, `POST /educator/learners/{id}/revoke` |
| Personalization | `GET /personalization/children/{id}/{profile,recommendations,progress,difficulty/{game}}` |
| Practice | `GET /remedial/activities`, `GET /remedial/children/{id}/next-activity`, `POST /remedial/sessions[/{id}/start\|events\|complete\|abandon]`, `GET /remedial/children/{id}/practice/progress` |
| Gaze and speech | `/gaze/trials/{id}/gaze[/features]`, `/speech/sessions[...]`, `/speech/analyze`, `/speech/demo/*` |
| Screening | `GET /screening/children/{id}`: status + observations; a percentage only from an eligible validated model |
| Research (off by default) | `GET /screening/research/children/{id}`, `POST /screening/research/children/{id}/assessments/{aid}/predict` (owner or granted educator); `GET /screening/research-demo/assessments/{id}` (admin) |
| ML (research) | `/ml/features/session/{id}`, `/ml/profile/session/{id}`, `/ml/predict/session/{id}` (always `unavailable`), `/ml/models`, `/ml/quality` (admin) |
| Privacy | `GET /privacy/data-summary`, `GET /privacy/export`, `DELETE /privacy/account` (password required) |
| Lexi | `GET /chat/status`, `GET/POST /chat/conversations`, `GET/DELETE /chat/conversations/{id}`, `GET/POST /chat/conversations/{id}/messages` |
| Operations | `GET /health` (liveness), `GET /health/ready` (database + schema revision; used by the container healthcheck) |

## Testing and Verified Results

```bash
# Backend (isolated temporary SQLite DB; never touches dyscover.db)
cd backend
python -m pytest                         # speech-ML modules are reported as skipped unless requirements-speech-ml.txt is installed
TEST_DATABASE_URL=postgresql+psycopg://pgtest:pgtest@127.0.0.1:55432/dyscover_test python -m pytest   # an EMPTY PostgreSQL database
#   disposable PostgreSQL: docker run -d --rm --name dyscover-pgtest -e POSTGRES_USER=pgtest -e POSTGRES_PASSWORD=pgtest -e POSTGRES_DB=dyscover_test -p 127.0.0.1:55432:5432 postgres:16-alpine
python -m app.ml.screening.verify        # research artifact checksum, fresh-process load, registry eligibility
pip-audit -r requirements.txt
LIVE_GROQ=1 LIVE_GROQ_API_KEY=... python -m pytest tests/test_chat.py -k live   # optional real Groq request

# Frontend
cd frontend
npx tsc -b --noEmit && npx eslint . && npx vitest run && npm run build
npx playwright test                      # starts its own backend (temp DB, migrations) + Vite
```

Fresh results on the final tree (2026-10-21):

| Check | Result |
|---|---|
| Backend pytest (SQLite, full stack) | **431 passed**, 1 skipped (live Groq; run separately below) |
| Backend pytest on PostgreSQL 16 | **344 passed** (API install); upgrade 0003→0004 with data, rollback, backup and restore, no orphans, zero schema diff |
| Live Groq test | 1 passed |
| TypeScript / ESLint / Vitest / build | 0 errors / 0 errors / **160 passed** / OK |
| Playwright (real backend) | **19 passed**: auth, sharing, all 8 games, research predictor, Lexi, EN/TA, privacy, mobile, axe |
| Docker Compose production stack | Builds, healthy, smoke-tested through nginx |

Details and evidence: [`docs/readiness/final-integration-report.md` §8](docs/readiness/final-integration-report.md).

## Deployment

See [`docs/deployment.md`](docs/deployment.md). It covers:
- server preparation and the environment-variable checklist;
- build, start and explicit migrations;
- TLS reverse-proxy example and smoke tests;
- daily `pg_dump` backups, verified restore, upgrade and rollback.

PostgreSQL and the API are never published; only nginx is.

## Project Structure

```
backend/
  app/
    access.py            ownership checks used by every router
    auth/ children/ assessments/ educator/ personalization/ remedial/
    chat/                Lexi (Groq provider, conversations)
    gaze/ speech/        optional modalities
    privacy/             export, data summary, deletion
    ml/                  features, synthetic simulator, quality, speech ML
    ml/screening/        schema, training, registry + eligibility gate, service,
                         research_data, research inference, verify, routes
    core/                config (fail-safe), migrations, rate limiting
    models.py            ORM models
  alembic/versions/      0001 baseline → 0002 auth/Lexi → 0003 screening → 0004 research predictions
  artifacts/             synthetic datasets and the research model artifact
  tests/                 pytest (security, IDOR, privacy, migrations, screening, research, …)
frontend/
  src/app/               dashboards, ScreeningCard, ResearchPredictor, account
  src/games/             8 games, runners, practice
  src/chatbot/ src/l10n/ src/gaze/ src/speech/ src/services/apiClient.ts
  e2e/                   Playwright journeys against the real API
docs/                    architecture, ML, privacy, deployment, readiness records
docker-compose.yml       postgres · migrate · backend · web
```

To change the schema: edit `models.py`, run `alembic revision --autogenerate -m "..."`, review the result, then `alembic upgrade head`. `tests/test_migrations.py` fails if models and migrations drift apart.

## Documentation

| Document | Description |
|---|---|
| [`docs/deployment.md`](docs/deployment.md) | Production deployment, environment checklist, backup/restore, upgrade, rollback |
| [`docs/readiness/project-completion-checklist.md`](docs/readiness/project-completion-checklist.md) | Release gate and remaining external tasks |
| [`docs/readiness/final-integration-report.md`](docs/readiness/final-integration-report.md) | What was verified, with commands and results |
| [`docs/readiness/ai-ml-validation.md`](docs/readiness/ai-ml-validation.md) | ML validation: synthetic results, screening gate, research predictor |
| [`docs/readiness/risk-register.md`](docs/readiness/risk-register.md) | Resolved defects and open risks |
| [`docs/readiness/implementation-state.md`](docs/readiness/implementation-state.md) | Implementation status by area |
| [`docs/privacy.md`](docs/privacy.md) | What is stored, shared and deleted |
| [`docs/ml-architecture.md`](docs/ml-architecture.md), [`docs/features.md`](docs/features.md), [`docs/evaluation.md`](docs/evaluation.md), [`docs/model-training.md`](docs/model-training.md) | Research ML subsystem |
| [`docs/speech-ml-pipeline.md`](docs/speech-ml-pipeline.md), [`docs/speech-architecture.md`](docs/speech-architecture.md) | Speech ML and provider architecture |
| [`docs/architecture/`](docs/architecture/) | System overview, backend, frontend, data model |

## Known Limitations and Remaining Work

| Kind | Item |
|---|---|
| Clinical | No labelled real-child data, external validation, specialist review or ethics approval. The clinical screening registry correctly stays empty |
| Devices | Real microphone and camera behaviour has not been verified on target devices (automated tests stub the browser speech API) |
| Before public access | Real host, DNS and TLS; off-host encrypted backups; monitoring; legal and privacy review; DPA with Groq; penetration test; MFA |
| Content | Specialist review of parent/educator copy; native-speaker review of the Tamil text, which was machine-authored |
| Optional | Frontend bundle splitting; transformers 5.x migration for speech ML; a non-executable model format |

Full list with owners: [project completion checklist](docs/readiness/project-completion-checklist.md).

## Roadmap

- [x] Eight games with server-side storage and scoring
- [x] Authentication, authorization, sharing, privacy export and deletion
- [x] Lexi assistant with saved conversations
- [x] English and Tamil interface
- [x] Screening schema, eligibility gate and honest parent card
- [x] Synthetic research predictor, end to end
- [x] PostgreSQL validation, Docker deployment and a deployment guide
- [ ] Ethically approved, labelled real-child data collection
- [ ] Clinical validation study and specialist-approved thresholds
- [ ] Real-device speech and gaze evaluation; Whisper fine-tuning on licensed child speech
- [ ] Longitudinal progress tracking and multimodal research
- [ ] Edge deployment (ONNX/quantization; see [`docs/speech-architecture.md`](docs/speech-architecture.md))

## License and Attributions

The project is intended to be released under the **MIT License**. The repository does not contain a `LICENSE` file yet; add one before distribution.

| Component | License | Notes |
|---|---|---|
| React, Vite | MIT | |
| FastAPI, scikit-learn | MIT, BSD-3-Clause | |
| WebGazer.js | **GPLv3** (separate commercial licence available) | Loaded at runtime from its own distribution; legal review needed before commercial use |
| Whisper, Hugging Face Transformers, PyTorch, jiwer | MIT, Apache 2.0, BSD-3-Clause, Apache 2.0 | Optional speech-ML tooling |
| Groq API | Groq terms of service | Lexi; requires your own API key |

Speech datasets must declare their licence in the manifest (for example Mozilla Common Voice, CC0).

---

> **Dyscover:** *a little world built around how children learn.*
> Version 0.2.0 · Research/educational demo · No clinical model deployed
