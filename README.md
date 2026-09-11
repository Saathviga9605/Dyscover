# Dyscover

Dyscover is an AI-assisted, gamified early screening and support platform concept for children approximately ages 4-10. It uses interactive activities to observe learning-related interaction patterns. Dyscover is **not a diagnostic or clinical system**.

## Stage 1-3.5 status

Stages 1 and 2 provide the product foundation and unified five-game assessment engine. Stage 3 adds research-safe feature extraction, semantic validation, subject-level dataset splitting, baseline model interfaces, model registry state, screening profiles, and parent-facing observed summaries. Stage 3.5 hardens feature governance, dataset artifacts, grouped folds, explicit model lifecycle, quality states, and reproducibility metadata.

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

## Architecture

- `frontend/src/games/registry.ts` defines a reusable `GameDefinition`, `GameInstance`, and callback contract.
- `frontend/src/gaze/types.ts` isolates providers such as WebGazer from games.
- `backend/app/models.py` stores users, child profiles, assessment sessions, game sessions, trials, events, gaze samples, fixations, and feature vectors.
- `backend/app/assessment.py` defines assessment domains and research feature names.
- API boundary data is validated with Pydantic; frontend requests go through `services/apiClient.ts`.
- `backend/app/ml` contains feature metadata, behavioral extraction, quality validation, subject-level dataset splitting, baseline model interfaces, explainability helpers, and research APIs.

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

## Next stage

Next work should focus on validated dataset collection, authentication/authorization, explicit consented gaze integration, speech/NLP feature providers, grouped evaluation on real labels, and deeper research experiments. Deep learning and multimodal fusion remain future work. See `docs/stage-3.5-hardening.md`.
