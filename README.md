# Dyscover

> **An AI-assisted, gamified early screening and support platform for children ages 4–10.**  
> Observes learning-related interaction patterns through playful, structured activities.  
> **Not a diagnostic or clinical system.** No validated clinical model is included.

---

## Table of Contents

- [Project Overview](#project-overview)
- [System Architecture](#system-architecture)
- [Assessment Domains](#assessment-domains)
- [Research ML Pipeline](#research-ml-pipeline)
- [Speech Recognition Pipeline](#speech-recognition-pipeline)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Overview](#api-overview)
- [Development](#development)
- [Testing](#testing)
- [Documentation](#documentation)
- [Privacy & Ethics](#privacy--ethics)
- [Roadmap](#roadmap)
- [License](#license)

---

## Project Overview

Dyscover is a research-grade platform that helps families, educators, and researchers **notice** learning patterns in children through structured, game-based activities. It does **not** diagnose dyslexia or any learning difference. Instead, it produces structured observational data that can inform conversations and guide next steps with professionals.

### Key Principles

| Principle | Description |
|-----------|-------------|
| **Non-diagnostic** | Never produces clinical labels, probabilities, or diagnoses |
| **Research-mode** | All ML outputs explicitly marked `unavailable` until validated labels exist |
| **Privacy-first** | No child identity in features; raw audio/video never stored; gaze/speech optional and consent-gated |
| **Modularity** | Provider abstraction for gaze, speech, and future modalities |
| **Reproducibility** | Deterministic splits, versioned configs, experiment registry, artifact hashes |

### What Dyscover Does

- Runs short, engaging activities (visual, auditory, speech-based)
- Captures interaction events, timing, accuracy, optional gaze & speech
- Extracts structured behavioral features with explicit availability metadata
- Provides parent-facing summaries of **observed patterns only**
- Supports offline ML research with subject-level splits and baseline models

### What Dyscover Does Not Do

- ❌ Diagnose dyslexia, ADHD, or any condition
- ❌ Calculate "dyslexia probability" or risk scores
- ❌ Replace professional evaluation
- ❌ Store raw camera/microphone data
- ❌ Use child identity as a model feature

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DYSCOVER SYSTEM                                 │
├──────────────────────────────┬──────────────────────────────────────────────┤
│         FRONTEND (React)     │           BACKEND (FastAPI)                  │
├──────────────────────────────┼──────────────────────────────────────────────┤
│  • Child Explorer Space      │  • REST API (OpenAPI/Swagger)                │
│  • Parent Dashboard          │  • PostgreSQL (prod) / SQLite (dev)          │
│  • Game Adapters             │  • SQLAlchemy ORM + Pydantic validation      │
│  • Gaze Provider Interface   │  • Provider abstraction (gaze, speech)       │
│  • i18n (EN/TA)              │  • Research ML subsystem (isolated)          │
│  • Accessibility (WCAG 2.1)  │  • Experiment registry & artifact tracking   │
└──────────────────────────────┴──────────────────────────────────────────────┘
```

### Data Model Hierarchy

```
User
└── ChildProfile
    └── AssessmentSession (versioned, localized)
        └── GameSession (per game definition)
            └── Trial (stimulus → response → correctness → timing)
                ├── InteractionEvent (typed event stream)
                ├── GazeSample / Fixation (optional, consented)
                └── SpeechSession (optional, consented)
                    └── Transcript + Alignment + Features
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Vitest, React Router, CSS Modules |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| Database | PostgreSQL (production), SQLite (development) |
| ML Research | scikit-learn, Hugging Face Transformers, PyTorch, Accelerate |
| Speech ML | Whisper (HF), jiwer, torchaudio, librosa, soundfile |
| Gaze | WebGazer.js (provider-isolated) |
| Testing | pytest, Vitest, React Testing Library |

---

## Assessment Domains

Defined in `backend/app/assessment.py` and mirrored in frontend types.

| Domain | Code | Description |
|--------|------|-------------|
| Visual Symbol Discrimination | `visual-symbol-discrimination` | Distinguish similar symbols/letters |
| Orthographic Recognition | `orthographic-recognition` | Recognize word forms and patterns |
| Phonological Awareness | `phonological-awareness` | Sound structure of language |
| Working Memory | `working-memory` | Hold and manipulate information |
| Sequencing | `sequencing` | Order and pattern reproduction |
| Attention / Visual Search | `attention-visual-search` | Sustained and selective attention |
| Reading Fluency | `reading-fluency` | Speed, accuracy, prosody in reading |
| Interaction Behavior | `interaction-behavior` | Response patterns, hesitations, pauses |

> **Note:** These are **dimensions for structured observation**, not individual diagnoses.

### Current Games (Stage 1–4)

| Game | Domain | Modality | Description |
|------|--------|----------|-------------|
| Letter Detective | Visual Symbol Discrimination | Visual | Spot the odd lowercase letter |
| Mirror Match | Visual Symbol Discrimination | Visual | Find the exact twin symbol |
| Word Flash | Orthographic Recognition | Visual | Catch and recall flashed words |
| Sequence Quest | Sequencing | Visual | Watch and repeat symbol order |
| Word Maze | Orthographic Recognition | Visual | Navigate to target words |
| Sound Quest Adventure | Phonological Awareness | Speech | Say words to advance story |
| Letter Bubble Pop | Phonological Awareness | Speech | Pop bubbles by speaking letters |
| Maze Runner Rush | Reading Fluency | Speech | Name words on a path |

---

## Research ML Pipeline

Located in `backend/app/ml/` — **isolated research subsystem**.

### Pipeline Flow

```
AssessmentSession
    → Trial/Event validation
    → Feature extraction (behavioral, gaze, speech, text)
    → Dataset rows (subject_id, session_id, features, target)
    → Subject-level split (train/val/test, no leakage)
    → Offline baseline training (Logistic, RF, GBM, Dummy)
    → Model registry (versioned, hashed, integrity-checked)
    → Optional inference → Screening profile (observations only)
```

### Key Guarantees

- **Subject-level splits** — no data leakage across train/val/test
- **Semantic validation** — invalid records rejected before modeling
- **Feature registry** — canonical names, units, domains, availability
- **Synthetic purity** — synthetic data never silently mixed with real
- **Model registry** — statuses: `unavailable | trained | validated | deprecated | failed`
- **Artifact integrity** — SHA256 hashes on checkpoints and manifests

### Available Baselines

| Algorithm | Status | Use Case |
|-----------|--------|----------|
| Dummy (prior/stratified) | ✅ | Sanity baseline |
| Logistic Regression | ✅ | Interpretable linear |
| Random Forest | ✅ | Non-linear, robust |
| Gradient Boosting | ✅ | Strong non-linear |

> **No clinical model is registered.** Prediction endpoints return `status: "unavailable"` with observed features and limitations.

### Synthetic Research Predictor

A trained, saved model (`backend/artifacts/screening-synthetic/dyscover-research-synthetic/`, gradient boosting, sigmoid-calibrated, v1.0.0) runs on a child's **real stored game results** and shows its output on a separate research page (`/research/predictor`). It was trained **only on synthetic data** whose labels are simulator settings, so its output is the probability of the *synthetic* target under this model — **not** a real-child dyslexia probability. It is off by default (`RESEARCH_DEMO_ENABLED=false`), refused in production, never shown on the parent screening card, and stored separately (`research_predictions`). Dataset, label rules and metrics: [`docs/readiness/ai-ml-validation.md` §9](docs/readiness/ai-ml-validation.md).

### Research Commands

```bash
cd backend

# Dataset split info
python -m app.ml split-info

# Synthetic data generation (research only)
python -m app.ml.synthetic.cli generate --help

# Train, evaluate and save the synthetic research predictor (~15 s; seed 42 reproduces the same artifact SHA-256)
python -m app.ml.screening.training --synthetic-demo --version 1.0.0 --output artifacts/screening-synthetic/dyscover-research-synthetic

# Verify saved artifacts in a fresh process (checksum, runtime, which registry may serve them)
python -m app.ml.screening.verify
```

To use the research predictor locally, set `RESEARCH_DEMO_ENABLED=true` in `backend/.env`, restart the backend, play the visual adventures for a child, then open **Open the synthetic research predictor** on the parent dashboard (or `/research/predictor`).

---

## Speech Recognition Pipeline

Located in `backend/app/ml/speech/` — complete Whisper fine-tuning & evaluation.

### Overview

| Component | Purpose |
|-----------|---------|
| **Dataset** | JSONL/CSV manifests, validation, deterministic speaker-aware splits |
| **Audio** | Resample 16kHz, mono, loudness norm (-20 dBFS), validation |
| **Model** | Whisper via HF Transformers (tiny/base/small/medium/large) |
| **Training** | Seq2SeqTrainer, gradient checkpointing, FP16/BF16, early stopping |
| **Evaluation** | WER/CER with jiwer, text normalization, per-sample & aggregate |
| **Experiment** | Config, registry, reproducibility reports (Markdown + JSON) |
| **CLI** | validate, split, train, evaluate, compare, create-experiment, run-experiment |
| **API** | `/api/speech/demo/*` — upload, transcribe, compare providers |
| **Frontend** | `SpeechDemo` React component |

### Supported Languages

`en, ta, hi, bn, te, mr, gu, kn, ml, pa, or, as` (12 languages)

### Quick Start

```bash
cd backend

# 1. Prepare manifest (JSONL)
cat > data/manifest.jsonl <<'EOF'
{"sample_id": "cv-001", "audio_path": "audio/cv-001.wav", "transcript": "the quick brown fox", "language": "en", "split": "train", "speaker_id": "spk-001", "source_dataset": "common_voice", "license": "CC0", "duration_seconds": 2.3}
{"sample_id": "cv-002", "audio_path": "audio/cv-002.wav", "transcript": "jumps over the lazy dog", "language": "en", "split": "train", "speaker_id": "spk-002", "source_dataset": "common_voice", "license": "CC0", "duration_seconds": 2.1}
EOF

# 2. Validate
python -m app.ml.speech.cli validate --manifest data/manifest.jsonl --base-dir data/

# 3. Create deterministic splits (speaker-aware)
python -m app.ml.speech.cli split \
  --manifest data/manifest.jsonl \
  --output-dir data/splits \
  --seed 42 \
  --speaker-aware

# 4. Fine-tune (smoke test: CPU, 1 epoch, 10 steps)
python -m app.ml.speech.cli train \
  --model openai/whisper-tiny \
  --train-manifest data/splits/manifest_train.jsonl \
  --val-manifest data/splits/manifest_validation.jsonl \
  --output-dir outputs/whisper-smoke \
  --epochs 1 --max-steps 10

# 5. Full training (GPU recommended)
python -m app.ml.speech.cli train \
  --model openai/whisper-base \
  --train-manifest data/splits/manifest_train.jsonl \
  --val-manifest data/splits/manifest_validation.jsonl \
  --output-dir outputs/whisper-finetune \
  --epochs 5 --fp16 --grad-checkpoint

# 6. Evaluate on held-out test set
python -m app.ml.speech.cli evaluate \
  --model outputs/whisper-finetune \
  --test-manifest data/splits/manifest_test.jsonl

# 7. Compare pretrained vs fine-tuned
python -m app.ml.speech.cli compare \
  --pretrained-model openai/whisper-base \
  --finetuned-model outputs/whisper-finetune \
  --test-manifest data/splits/manifest_test.jsonl
```

### Enable Whisper Provider in API

```bash
# backend/.env
DYSCOVER_ASR_PROVIDER=huggingface-whisper
DYSCOVER_HF_WHISPER_MODEL=openai/whisper-tiny
DYSCOVER_HF_WHISPER_LANGUAGE=en
DYSCOVER_HF_WHISPER_DEVICE=auto
DYSCOVER_HF_WHISPER_DTYPE=float32
```

### Demo Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/speech/demo/providers` | List available providers & status |
| POST | `/api/speech/demo/transcribe` | Transcribe uploaded audio (multipart, consent required) |
| POST | `/api/speech/demo/compare` | Compare all providers on same audio |
| GET | `/api/speech/demo/models` | Show configured model parameters |

### Frontend Demo

```tsx
import { SpeechDemo } from '@/speech';

function MyPage() {
  return <SpeechDemo />;
}
```

### Reproducibility

Every experiment records:
- Experiment ID, name, description
- Base model + revision, dataset name/version/manifest hash
- Split seed & strategy, language
- Full training & evaluation configs
- Environment: Python, PyTorch, Transformers, CUDA versions
- Timestamps: created / started / completed
- Status: `created | training | evaluating | completed | failed`
- Artifact paths + SHA256 hashes

Outputs: `experiment_report.md`, `experiment_metadata.json`, model checkpoints.

### Documentation

- **Full pipeline docs:** [`docs/speech-ml-pipeline.md`](docs/speech-ml-pipeline.md)
- **Architecture & provider integration:** [`docs/speech-architecture.md`](docs/speech-architecture.md)

---

## Quick Start

### Prerequisites

- Python 3.13, Node.js 22+
- Optional: Docker (for the PostgreSQL deployment), a Groq API key (for Lexi)

### Backend (development, SQLite)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env              # optional: GROQ_API_KEY, DATABASE_URL, ...
uvicorn app.main:app --reload     # applies Alembic migrations automatically in development
```

API docs: http://localhost:8000/docs (disabled when `APP_ENV=production`).

### Frontend

```bash
cd frontend
npm ci
npm run dev                       # http://localhost:5173 ; /api is proxied to :8000
```

Register a parent account, add a child profile on the parent dashboard, then choose **Start screening**. Educators register separately; a parent shares a child with an educator by the educator's account email.

### Production-style stack (Docker Compose)

```bash
cp .env.example .env              # set POSTGRES_PASSWORD and SECRET_KEY (>= 32 random chars)
docker compose up -d --build      # postgres -> migrate (alembic upgrade head) -> backend -> web
# open http://localhost:8080  (put TLS in front of "web" for any real deployment)
```

The API is not published directly; nginx serves the SPA and proxies `/api`. See `docs/readiness/final-integration-report.md` for what has and has not been verified.

## Configuration

Backend settings come from environment variables (or `backend/.env`):

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` or `production` |
| `SECRET_KEY` | dev-only key | **Required in production**, ≥32 random characters |
| `DATABASE_URL` | `sqlite:///./dyscover.db` | PostgreSQL: `postgresql+psycopg://user:pass@host:5432/db` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated exact origins; `*` refused in production |
| `AUTO_MIGRATE` | on outside production | Production expects `alembic upgrade head` as a release step |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | 15 / 7 | Session lifetimes |
| `REFRESH_COOKIE_SECURE` / `REFRESH_COOKIE_SAMESITE` | secure in production / `lax` | |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_CHAT` | on, `10/minute`, `20/minute` | |
| `GROQ_API_KEY`, `GROQ_MODEL` | empty, `openai/gpt-oss-120b` | Without a key Lexi reports "not configured" |
| `DYSCOVER_ASR_PROVIDER` (+ model vars) | unset | Optional local Whisper for the speech demo |
| `SCREENING_MODEL_DIR` | `models/screening` | Production screening models; only models passing every eligibility check are used |
| `RESEARCH_DEMO_ENABLED`, `RESEARCH_DEMO_MODEL_DIR` | `false`, `artifacts/screening-synthetic` | Synthetic research predictor; refused when `APP_ENV=production` |

Frontend: `VITE_API_URL` (default `/api`, same-origin), `VITE_PROXY_TARGET` (dev proxy target, default `http://localhost:8000`).

## API Overview

All endpoints are under `/api`; the live schema is at `/docs` in development. Every endpoint except health, registration/login/refresh/logout and static status endpoints requires `Authorization: Bearer <access token>`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`*, `/auth/logout`*, `/auth/logout-all`, `/auth/change-password`; `GET /auth/me` (*cookie + `X-Requested-With: dyscover`) |
| Children | `GET/POST /children`, `GET/PATCH/DELETE /children/{id}`, `GET/POST /children/{id}/educators`, `DELETE /children/{id}/educators/{educator_id}` |
| Assessments | `POST /assessments`, `GET /assessments/{id}`, `GET /children/{id}/assessments?limit&offset`, `POST /assessments/{id}/games/{game_id}/trials`, `POST|GET /trials/{id}/events`, `POST /assessments/{id}/summary`, `GET /assessments/{id}/modality-summary` |
| Educator | `GET /educator/learners`, `GET /educator/learners/{id}/summary`, `POST /educator/learners/{id}/revoke` |
| Personalization / practice | `/personalization/children/{id}/{profile,recommendations,progress,difficulty/{game}}`, `/remedial/...` |
| Gaze / speech | `/gaze/trials/{id}/gaze[/features]`, `/speech/sessions[...]`, `/speech/analyze`, `/speech/demo/*` |
| Screening | `GET /screening/children/{id}` (status + observations; a percentage only from an eligible validated model), `GET /screening/research/children/{id}` and `POST /screening/research/children/{id}/assessments/{aid}/predict` (synthetic research predictor; owner or granted educator; off by default), `GET /screening/research-demo/assessments/{id}` (admin, off by default) |
| ML (research) | `/ml/features/session/{id}`, `/ml/profile/session/{id}`, `/ml/predict/session/{id}` (always `unavailable`), `/ml/models`, `/ml/quality` (admin) |
| Privacy | `GET /privacy/data-summary`, `GET /privacy/export`, `DELETE /privacy/account` (password) |
| Lexi | `GET /chat/status`, `GET/POST /chat/conversations`, `GET/DELETE /chat/conversations/{id}`, `GET/POST /chat/conversations/{id}/messages` |
| Operations | `GET /health` (liveness), `GET /health/ready` (database + schema revision) |

## Development

```
backend/app/
  access.py          resource ownership checks used by every router
  auth/ children/ assessments/ educator/ chat/ privacy/
  gaze/ speech/ personalization/ remedial/ ml/
  core/              config (fail-safe), migrations, rate limiting, time
  models.py          ORM models (schema changes need an Alembic migration)
backend/alembic/versions/   authoritative schema history
frontend/src/
  auth/ app/ chatbot/ games/ gaze/ speech/ l10n/ services/apiClient.ts
frontend/e2e/       Playwright journeys against the real API
```

Schema changes: edit `models.py`, then `alembic revision --autogenerate -m "..."`, review, and `alembic upgrade head`. `tests/test_migrations.py` fails if models and migrations drift.

## Testing

```bash
# Backend (isolated temporary SQLite DB; never touches dyscover.db)
cd backend
pytest                                   # all tests incl. speech-ML (needs requirements-speech-ml.txt)
pytest --ignore=tests/ml/speech          # API + ML without the heavy speech stack
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/empty_db pytest   # run against PostgreSQL
pip-audit -r requirements.txt            # dependency vulnerabilities
LIVE_GROQ=1 LIVE_GROQ_API_KEY=... pytest tests/test_chat.py -k live   # optional real Groq request

# Frontend
cd frontend
npm run typecheck && npm run lint && npm test && npm run build
npx playwright test                      # starts its own backend (temp DB) + Vite; Lexi uses a test echo provider
```

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/speech-ml-pipeline.md`](docs/speech-ml-pipeline.md) | Complete Whisper fine-tuning & evaluation guide |
| [`docs/speech-architecture.md`](docs/speech-architecture.md) | Provider abstraction, API integration, edge deployment roadmap |
| [`docs/ml-architecture.md`](docs/ml-architecture.md) | Research ML subsystem architecture |
| [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md) | System boundaries & data flow |
| [`docs/architecture/backend.md`](docs/architecture/backend.md) | Backend module structure |
| [`docs/architecture/frontend.md`](docs/architecture/frontend.md) | Frontend architecture & patterns |
| [`docs/architecture/data-model.md`](docs/architecture/data-model.md) | ERD & schema details |
| [`docs/features.md`](docs/features.md) | Feature definitions & metadata |
| [`docs/evaluation.md`](docs/evaluation.md) | Evaluation methodology |
| [`docs/privacy.md`](docs/privacy.md) | Privacy principles |
| [`docs/model-training.md`](docs/model-training.md) | Training governance |
| [`docs/assessment/assessment-model.md`](docs/assessment/assessment-model.md) | Assessment domain model |

---

## Privacy & Ethics

See [docs/privacy.md](docs/privacy.md) for exactly what is stored, shared and deleted.

- **Not a diagnosis.** Games produce observations; no model has been validated on real children, and prediction is disabled.
- **Missing ≠ zero.** Unrecorded gaze/speech stays `null`/unavailable; failed speech recognition is not counted as a reading error.
- **Consent-gated capture.** Camera and microphone are used only after an adult opts in; no video or audio is stored.
- **Owner-only access.** Each child's data is visible only to the parent account that created it, plus read-only summaries for educators the parent chooses.
- **External services.** Lexi messages are sent to Groq; browser speech recognition may send audio to the browser vendor. Both are disclosed in the app.
- **Export and erasure** are available from the account page.
- Compliance with COPPA, GDPR, the UK Children's Code or India's DPDP Act has **not** been assessed; see `docs/readiness/risk-register.md`.

---

## Roadmap

### Near Term (Stage 5+)

- [x] Authentication & authorization (JWT + rotating refresh cookie, roles, ownership checks)
- [ ] Validated labeled dataset collection pipeline
- [ ] Explicit consented gaze integration (WebGazer calibration UX)
- [ ] Configured speech providers in production
- [ ] Grouped evaluation on real labels
- [ ] Deeper research experiments (multimodal fusion)

### Medium Term

- [ ] Clinical speech model evaluation (not deployment)
- [ ] Multimodal fusion (gaze + speech + behavioral)
- [ ] Parent/educator collaboration features
- [ ] Longitudinal tracking & growth curves

### Future (Edge Deployment)

*See [`docs/speech-architecture.md#edge-deployment-future-work`](docs/speech-architecture.md#edge-deployment-future-work)*

- [ ] Model export to ONNX/TFLite/CoreML
- [ ] INT8/INT4 quantization with accuracy validation
- [ ] Runtime selection (ONNX Runtime, TensorRT, whisper.cpp)
- [ ] Hardware benchmarking (Raspberry Pi, Jetson, mobile)
- [ ] Streaming/chunked inference for real-time
- [ ] On-device privacy validation

---

## License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE) for details.

### Third-Party Attributions

| Component | License | Source |
|-----------|---------|--------|
| Whisper (OpenAI) | MIT | https://github.com/openai/whisper |
| Hugging Face Transformers | Apache 2.0 | https://github.com/huggingface/transformers |
| PyTorch / torchaudio | BSD-3-Clause | https://pytorch.org |
| jiwer | Apache 2.0 | https://github.com/jitsi/jiwer |
| scikit-learn | BSD-3-Clause | https://scikit-learn.org |
| WebGazer.js | MIT | https://webgazer.cs.brown.edu |
| React / Vite | MIT | https://react.dev / https://vitejs.dev |

### Dataset Licenses

- **Mozilla Common Voice** — CC0 (public domain)
- **LibriSpeech** — Public domain
- **Custom datasets** — Must specify license in manifest

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes with tests
4. Run `pytest` and `npm run test`
5. Submit a Pull Request

### Commit Convention

```
feat: add new game definition
fix: handle empty transcript in validation
docs: update speech pipeline quickstart
refactor: extract audio preprocessing to module
test: add speaker-aware split test
```

---

## Support & Contact

- **Issues:** [GitHub Issues](https://github.com/your-org/dyscover/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-org/dyscover/discussions)
- **Email:** research@dyscover.example.com

---

## Acknowledgments

- Families and educators who provided feedback on early prototypes
- Open-source communities: Hugging Face, PyTorch, scikit-learn, React
- Research advisors in computational linguistics and developmental psychology

---

> **Dyscover** — *A little world built around how children learn.*  
> **Version:** 0.1.0 (Stage 4 — Speech & Reading Infrastructure)  
> **Status:** RESEARCH MODE — No clinical model deployed