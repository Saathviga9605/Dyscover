# Dyscover

Dyscover is an AI-assisted, gamified early screening and support platform concept for children approximately ages 4-10. It uses interactive activities to observe learning-related interaction patterns. Dyscover is **not a diagnostic or clinical system**.

## Stage 1 status

Stage 1 establishes the product foundation without inventing clinical results: a React/TypeScript/Vite frontend, FastAPI backend, SQLAlchemy/PostgreSQL-ready data layer, typed assessment contracts, modular game definitions, gaze interfaces, API contracts, and route-level UX shells.

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

Backend routes: `/api/health`, `/api/version`, child profiles, assessment sessions, game sessions, trials, interaction events, and child assessment history. See `docs/architecture/backend.md`.

## Architecture

- `frontend/src/games/registry.ts` defines a reusable `GameDefinition`, `GameInstance`, and callback contract.
- `frontend/src/gaze/types.ts` isolates providers such as WebGazer from games.
- `backend/app/models.py` stores users, child profiles, assessment sessions, game sessions, trials, events, gaze samples, fixations, and feature vectors.
- `backend/app/assessment.py` defines assessment domains and research feature names.
- API boundary data is validated with Pydantic; frontend requests go through `services/apiClient.ts`.

## Privacy and limitations

Stage 1 does not load WebGazer, collect camera/audio data, run ML, calculate dyslexia probabilities, or produce clinical predictions. Gaze fields and feature vectors are storage contracts for future, consent-based research work. Do not place secrets or personal child data in frontend code or URLs.

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

## Next stage

Stage 2 should implement one accessible activity end to end, consent and session lifecycle, server-side event ingestion, validated scoring descriptors, and focused usability/research instrumentation. It should not introduce diagnosis or unsupported probabilities.
