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
- [API Reference](#api-reference)
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

### Research Commands

```bash
cd backend

# Dataset split info
python -m app.ml split-info

# Synthetic data generation (research only)
python -m app.ml.synthetic.cli generate --help
```

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

- **Node.js 20+** (frontend)
- **Python 3.11+** (backend)
- **PostgreSQL 14+** (production) or SQLite (development)
- **GPU optional** (for Whisper fine-tuning)

### Frontend

```bash
cd frontend
npm install
npm run dev          # Development server (Vite)
npm run build        # Production build
npm run test         # Unit tests (Vitest)
```

Environment variable:
```bash
VITE_API_URL=http://localhost:8000/api  # Default
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with DATABASE_URL, CORS_ORIGINS, ASR provider settings

uvicorn app.main:app --reload
```

API available at `http://localhost:8000`  
Swagger UI at `http://localhost:8000/docs`

---

## Configuration

### Backend Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./dyscover.db` | PostgreSQL connection string for production |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `DYSCOVER_ASR_PROVIDER` | *(empty)* | `huggingface-whisper` or `faster-whisper` |
| `DYSCOVER_HF_WHISPER_MODEL` | `openai/whisper-tiny` | HF model ID or local path |
| `DYSCOVER_HF_WHISPER_LANGUAGE` | `en` | Default transcription language |
| `DYSCOVER_HF_WHISPER_DEVICE` | `auto` | `auto`, `cpu`, `cuda`, `mps` |
| `DYSCOVER_HF_WHISPER_DTYPE` | `float32` | `float32`, `float16`, `bfloat16` |
| `DYSCOVER_HF_WHISPER_CACHE` | *(empty)* | Local cache directory for HF models |
| `DYSCOVER_ASR_MODEL` | `small` | faster-whisper model size |
| `DYSCOVER_ASR_MODEL_PATH` | *(empty)* | Local faster-whisper model path |
| `DYSCOVER_ASR_DEVICE` | `cpu` | faster-whisper device |
| `DYSCOVER_ASR_COMPUTE_TYPE` | `int8` | faster-whisper compute type |
| `DYSCOVER_ASR_ALLOW_MODEL_LOAD` | `false` | Must be `true` to load faster-whisper |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000/api` | Backend API base URL |

---

## API Reference

### Core Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/version` | Version info |

### Child & Assessment

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/children` | Create child profile |
| GET | `/api/children/{id}` | Get child profile |
| POST | `/api/assessments` | Create assessment session |
| GET | `/api/assessments/{id}` | Get assessment |
| POST | `/api/assessments/{id}/games` | Start game session |
| POST | `/api/games/{id}/trials` | Submit trial |
| POST | `/api/trials/{id}/events` | Submit interaction events |
| POST | `/api/assessments/{id}/summary` | Create assessment summary |

### ML Research

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ml/features/{session_id}` | Get feature vector |
| GET | `/api/ml/profile/{session_id}` | Get screening profile |
| GET | `/api/ml/models` | List registered models |
| GET | `/api/ml/quality` | Data quality report |

### Speech Research

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/speech/status` | Provider status |
| POST | `/api/speech/analyze` | Analyze reading (alignment + features) |
| POST | `/api/speech/sessions` | Create speech session |
| GET | `/api/speech/sessions/{id}` | Get speech session |
| POST | `/api/speech/sessions/{id}/features` | Store speech features |

### Speech Demo (requires consent)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/speech/demo/providers` | List providers & status |
| POST | `/api/speech/demo/transcribe` | Transcribe audio (multipart) |
| POST | `/api/speech/demo/compare` | Compare providers |
| GET | `/api/speech/demo/models` | Show model configs |

> **Consent required:** All demo endpoints require `consent=true` form field.

### Educator Routes (auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/educator/learners/{id}/authorize` | Authorize learner |
| POST | `/api/educator/learners/{id}/revoke` | Revoke access |
| GET | `/api/educator/learners` | List authorized learners |
| GET | `/api/educator/learners/{id}/summary` | Get learner summary |

---

## Development

### Project Structure

```
Dyscover/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── core/             # Config, security
│   │   ├── database.py       # SQLAlchemy engine/session
│   │   ├── models.py         # ORM models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── assessment.py     # Domain definitions
│   │   ├── ml/               # Research ML subsystem
│   │   │   ├── speech/       # Whisper pipeline
│   │   │   ├── synthetic/    # Synthetic data generator
│   │   │   └── ...           # Features, registry, training, eval
│   │   ├── speech/           # Provider abstraction
│   │   ├── gaze/             # Gaze provider & features
│   │   ├── personalization/  # Stage 5: difficulty, recommendations
│   │   ├── remedial/         # Practice activities
│   │   └── main.py           # FastAPI app factory
│   ├── tests/                # pytest suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components
│   │   ├── games/            # Game definitions & registry
│   │   ├── speech/           # SpeechDemo, analyzer, types
│   │   ├── gaze/             # WebGazer provider
│   │   ├── l10n/             # i18n (EN/TA)
│   │   ├── services/         # API client
│   │   └── styles/           # CSS modules
│   ├── package.json
│   └── vite.config.ts
└── docs/                     # Architecture & feature docs
```

### Code Conventions

- **Python**: Black formatting, type hints, Pydantic v2, SQLAlchemy 2.0
- **TypeScript**: Strict mode, functional components, React hooks
- **API**: Pydantic validation, explicit error responses, OpenAPI tags
- **Database**: Migrations via Alembic (not yet configured; uses `create_all`)
- **Git**: Conventional commits, no direct pushes to main

### Adding a New Game

1. Define `GameDefinition` in `frontend/src/games/registry.ts`
2. Implement game component with `GameInstance` callbacks
3. Add domain in `backend/app/assessment.py`
4. Register routes if new endpoints needed
5. Update feature extraction if new behavioral signals

---

## Testing

### Backend

```bash
cd backend

# All tests
pytest

# Specific modules
pytest tests/ml/speech/ -v
pytest tests/test_speech.py -v
pytest tests/test_ml.py -v

# Coverage
pytest --cov=app --cov-report=html
```

### Frontend

```bash
cd frontend
npm run test          # Vitest
npm run test:ui       # Vitest UI
npm run build         # TypeScript + Vite build
```

### Test Philosophy

- **Unit tests** for pure logic (alignment, normalization, feature extraction)
- **Integration tests** for API routes (TestClient)
- **ML tests** for dataset integrity, model serialization, leakage prevention
- **Synthetic data tests** for determinism, modality honesty, language boundaries
- **No external dependencies** in CI — mocks for HF models, torchcodec

---

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

### Data Handling

| Data Type | Storage | Retention |
|-----------|---------|-----------|
| Child profile (name, birth year) | Encrypted DB | Until deletion request |
| Interaction events | DB (pseudonymized) | Research configurable |
| Gaze samples | DB (optional) | With consent only |
| Speech audio | **Never stored** | N/A |
| Speech transcripts | DB (optional) | With consent only |
| Feature vectors | DB | Research configurable |

### Core Privacy Guarantees

- **No identity features** — child ID never used in ML
- **Missing ≠ zero** — unavailable modalities stay `null`/`unavailable`
- **Synthetic isolation** — research synthetic data never mixed with real
- **Consent-gated** — gaze/speech require explicit opt-in per session
- **No external calls** — all inference local; no cloud API keys required

### Compliance Considerations

- Designed for COPPA/GDPR alignment (pseudonymization, deletion, consent)
- Research-mode disclaimer on all ML outputs
- No clinical claims — explicit non-diagnostic positioning

---

## Roadmap

### Near Term (Stage 5+)

- [ ] Authentication & authorization (JWT, roles)
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