# Dyscover

Dyscover is an AI-assisted, gamified early screening and support platform concept for children approximately ages 4-10. It uses interactive activities to observe learning-related interaction patterns. Dyscover is **not a diagnostic or clinical system**.

## Stage 1-4 status

Stages 1 and 2 provide the product foundation and unified five-game assessment engine. Stage 3 adds research-safe feature extraction, semantic validation, subject-level dataset splitting, baseline model interfaces, model registry state, screening profiles, and parent-facing observed summaries. Stage 3.5 hardens feature governance, dataset artifacts, grouped folds, explicit model lifecycle, quality states, and reproducibility metadata. Stage 4 adds optional speech/reading infrastructure: provider abstraction, transcript schemas, alignment, reading-error representation, pause/fluency metrics, and deterministic NLP features.

The system is currently in **RESEARCH MODE**. No validated labeled dataset or trained clinical model is included. ML prediction endpoints explicitly return unavailable status; observed activity data remains available. Dyscover does not diagnose dyslexia and does not calculate arbitrary dyslexia probabilities.

## Run locally

### Frontend

Requires Node.js 20+.

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` when the API is not at `http://localhost:8000/api`.

### Backend

Requires Python 3.11+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The default local database is SQLite. PostgreSQL is supported through `DATABASE_URL`; copy `.env.example` to `.env` and set the connection string. `CORS_ORIGINS` accepts a comma-separated list.

## Routes

Frontend public routes: `/`, `/about`, `/how-it-works`, `/research`, `/contact`.

Structural product routes: `/child/home`, `/child/assessment`, and `/parent/dashboard`.

Backend routes: `/api/health`, `/api/version`, child profiles, assessment sessions, game sessions, trials, interaction events, summaries, ML features, ML profiles, ML prediction availability, model registry, and data quality. See `docs/architecture/backend.md` and `docs/ml-architecture.md`.

Speech routes: `/api/speech/status`, `/api/speech/analyze`, `/api/speech/sessions`, and `/api/speech/sessions/{speech_session_id}`. See `docs/speech-architecture.md`.

## Architecture

- `frontend/src/games/registry.ts` defines a reusable `GameDefinition`, `GameInstance`, and callback contract.
- `frontend/src/gaze/types.ts` isolates providers such as WebGazer from games.
- `backend/app/models.py` stores users, child profiles, assessment sessions, game sessions, trials, events, gaze samples, fixations, and feature vectors.
- `backend/app/assessment.py` defines assessment domains and research feature names.
- API boundary data is validated with Pydantic; frontend requests go through `services/apiClient.ts`.
- `backend/app/ml` contains feature metadata, behavioral extraction, quality validation, subject-level dataset splitting, baseline model interfaces, explainability helpers, and research APIs.
- `backend/app/speech` contains provider-neutral transcript, alignment, reading, pause, fluency, and deterministic text feature infrastructure.

## Privacy and limitations

The ML layer does not use child identity as a feature, does not fabricate labels, and keeps unavailable modalities missing rather than replacing them with arbitrary values. Gaze fields are optional research signals. Do not place secrets or personal child data in frontend code or URLs.

## Legacy migration

The original HTML prototype remains in the repository as a reference surface. Its visual letter confusion, mirror matching, rapid word recognition, sequencing, word maze, speech interaction, gaze calibration, fixation metrics, and CSV column concepts are documented in `docs/architecture/legacy-migration.md`. The new routes do not load the legacy scripts or external Tenor/WebGazer/Chart.js assets.

## Development checks

```powershell
cd backend
pytest
python -m compileall -q app tests

cd ..\frontend
npm run build
npm run test
```

The frontend checks require Node.js. The current workspace may not have Node installed.

## Stage 3 research commands

```powershell
cd backend
python -m app.ml split-info
```

Offline model training is intentionally not run by the API and is not performed in this repository without validated labels. Add a governed dataset, configure an experiment, then train and evaluate outside normal request handling.

## Speech ML Pipeline (Stage 4+)

A complete Whisper fine-tuning and evaluation pipeline is available in `backend/app/ml/speech/`.

### Quick Commands

```powershell
cd backend

# Validate dataset manifest
python -m app.ml.speech.cli validate --manifest data/manifest.jsonl --base-dir data/

# Create train/val/test splits
python -m app.ml.speech.cli split --manifest data/manifest.jsonl --output-dir data/splits --seed 42

# Fine-tune Whisper (smoke test)
python -m app.ml.speech.cli train --model openai/whisper-tiny --train-manifest data/splits/manifest_train.jsonl --val-manifest data/splits/manifest_validation.jsonl --output-dir outputs/whisper-smoke --epochs 1 --max-steps 10

# Fine-tune Whisper (full)
python -m app.ml.speech.cli train --model openai/whisper-base --train-manifest data/splits/manifest_train.jsonl --val-manifest data/splits/manifest_validation.jsonl --output-dir outputs/whisper-finetune --epochs 5 --fp16

# Evaluate model
python -m app.ml.speech.cli evaluate --model outputs/whisper-finetune --test-manifest data/splits/manifest_test.jsonl

# Compare pretrained vs fine-tuned
python -m app.ml.speech.cli compare --pretrained-model openai/whisper-base --finetuned-model outputs/whisper-finetune --test-manifest data/splits/manifest_test.jsonl

# Run complete experiment
python -m app.ml.speech.cli create-experiment --name my-exp --model openai/whisper-base --manifest data/manifest.jsonl
python -m app.ml.speech.cli run-experiment --config outputs/experiments/my-exp-*/experiment_config.json
```

### Enable Whisper Provider

```powershell
# In backend/.env or environment
DYSCOVER_ASR_PROVIDER=huggingface-whisper
DYSCOVER_HF_WHISPER_MODEL=openai/whisper-tiny
DYSCOVER_HF_WHISPER_LANGUAGE=en
DYSCOVER_HF_WHISPER_DEVICE=auto
```

See `docs/speech-ml-pipeline.md` for full documentation.

## Next stage

Next work should focus on validated dataset collection, authentication/authorization, explicit consented gaze integration, configured speech providers, grouped evaluation on real labels, and deeper research experiments. Deep learning, clinical speech models, and multimodal fusion remain future work. See `docs/stage-3.5-hardening.md` and `docs/speech-architecture.md`.
