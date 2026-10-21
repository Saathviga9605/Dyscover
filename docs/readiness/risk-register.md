# Risk Register

Updated 2026-10-21. Part A lists defects **verified** in the code at the start of the 2026-10-20 pass and how they were resolved (with the test that now guards them). Part B lists **open** risks and limitations. Nothing here is a legal opinion or a security certification.

## A. Verified defects (resolved)

| # | Severity | Defect found | Resolution | Guarded by |
|---|---|---|---|---|
| A1 | Critical | Backend could not be imported (duplicate `practice_events` table spliced into `models.py`); no test could run. | Models rebuilt. | Whole suite |
| A2 | Critical | Children, assessments, trials, events, gaze, speech, ML, personalization and remedial endpoints had **no authentication**; any ID gave read/write access to child data. | Central ownership checks (`app/access.py`) on every router; 404 on denial. | `test_security.py` (route enumeration + IDOR matrix) |
| A3 | Critical | Educator identity taken from an `X-User-Id` header; educators could self-authorize access to any child. | Header identity removed; access granted only by the child's owner by educator email. | `test_educator_access.py` |
| A4 | Critical | Insecure default `secret_key = "changeme"` (Compose default too). | Production refuses empty/placeholder/short keys; dev uses a clearly-labelled dev key. | `test_production_refuses_insecure_secret_keys` |
| A5 | High | Privacy export included the user's **password hash**. | Export uses an explicit field allow-list. | `test_export_contains_own_data_and_never_credentials` |
| A6 | High | Account deletion deleted assessments before their summaries/feature vectors (orphans on SQLite, FK failure on PostgreSQL); conversations not deleted. | Ordered deletion service; transactional; password required. | `test_privacy.py` (SQLite and PostgreSQL) |
| A7 | High | Refresh tokens kept in process memory (lost on restart, not multi-worker safe), also returned to JavaScript; password change did not end other sessions. | DB-backed hashed rotating tokens, HttpOnly cookie only, `token_version`. | `test_refresh_rotates_and_detects_reuse`, `test_password_change_invalidates_other_sessions` |
| A8 | High | Rate limiter configured but never attached (no middleware/decorators). | `SlowAPIMiddleware` + per-route limits on auth, chat, export, uploads. | `test_login_is_rate_limited` |
| A9 | High | Migrations not authoritative: "initial" migration only added one index; Lexi migration had a dangling `down_revision`; startup used `create_all` + ad-hoc `ALTER TABLE`. | Real baseline + `0002`; startup migrates (dev) or verifies (prod). | `test_migrations.py` (zero autogenerate diff) |
| A10 | High | Frontend called `/api/api/auth/...` (double prefix) — login/registration could not work; access token in `localStorage`. | Same-origin client, memory-only token, cookie refresh. | Playwright `auth.spec.ts` |
| A11 | High | Lexi was hard-coded in the UI; backend chat route had a missing import, mislabelled history roles, blocked the event loop and never read `GROQ_API_KEY`. | Rewritten end to end. | `test_chat.py`, Playwright `lexi-language-privacy.spec.ts` |
| A12 | High | Clients could submit fabricated results (`correctness: true` with no or wrong answer). | Server-side scoring for the five visual games. | `test_assessment_integrity.py` |
| A13 | High | Speech-game microphone could start without consent ("Let's go" bypassed the gate), and the consent button itself was permanently disabled. | Start blocked until an adult consents; gate fixed. | Playwright `games.spec.ts` |
| A14 | Medium | Speech recognition failures/silence graded as wrong reading answers. | Stored unscored; excluded from difficulty adaptation. | Playwright speech run (all trials have ASR features) |
| A15 | Medium | Duplicate orphan assessment per run (effect ran twice). | Shared in-flight creation. | Playwright visual run (exactly one assessment) |
| A16 | Medium | Game state traps: Word Maze could not be finished without finding every word; pausing during a memory stimulus or during feedback froze the game; speech pause button did nothing; double taps could submit twice; aborted recognitions could be recorded on the previous trial. | Fixed in runners/views. | Playwright game runs |
| A17 | Medium | Speech demo: unauthenticated, whole upload read into memory before size check, `os.environ` mutated per request, blocking transcription in async handler, model reloaded per request, HF provider reported AVAILABLE without dependencies. | Rewritten. | Code review; `test_speech.py` |
| A18 | Medium | Offline queue blocked forever on a permanently rejected item; concurrent flushes could drop the wrong item; unbounded storage; queue/consent survived logout. | Fixed; account-scoped keys cleared on login/logout. | Unit tests |
| A19 | Medium | Vulnerable dependencies: starlette 0.41.3, python-jose 3.3.0 (+ ecdsa, unfixed advisories), python-multipart 0.0.20. | FastAPI 0.156.1 / Starlette 1.9.0, PyJWT 2.15.1, python-multipart 0.0.32. `pip-audit -r requirements.txt`: no known vulnerabilities. | `pip-audit` |
| A20 | Medium | WebGazer loaded unpinned from a university server without integrity check. | Pinned `webgazer@3.5.3` (byte-identical to what was served) with SRI; verified in Chromium that a wrong hash is blocked. | Manual check (recorded in final report) |
| A21 | Medium | Muted text failed WCAG AA contrast on tinted surfaces (axe: 9 nodes). | Token darkened to `#5a6575` (≥4.66:1 on every surface). | Playwright axe checks |
| A22 | Low | Tests wrote into the developer database `dyscover.db` (3 443 ownerless children accumulated). | Isolated temporary DB per run. | `tests/conftest.py` |
| A23 | Low | Contact form showed "sent" without sending anything. | Opens the user's email app; says so. | — |
| A24 | Low | ML pickle loader followed any path in the metadata file; median imputation erased missingness. | Plain file names only; missing-value indicators added. | `test_synthetic_ml.py` |

## B. Open risks and limitations

| # | Area | Risk | Current mitigation | Needed |
|---|---|---|---|---|
| B1 | Clinical | Users may read game observations as a diagnosis. | No predictive inference; non-clinical wording; disclaimers in UI and Lexi prompt. | Specialist review of all parent/educator copy. |
| B2 | ML validity | No real, labelled data; synthetic metrics only. | Production registry refuses synthetic models; `/predict` returns `unavailable`. | See `ai-ml-validation.md` §5. |
| B3 | Integrity | Stimuli are generated client-side; a modified client can submit a consistent-but-fake trial. | Server re-scores; anomalies recorded. | Server-issued stimuli if results ever inform decisions. |
| B4 | Privacy/legal | Children's data (incl. gaze coordinates, speech transcripts) is processed; Lexi text goes to Groq; some browsers send speech audio to their vendor. | Disclosures on account page and Lexi; consent gates; export/deletion. | Qualified legal review (COPPA, GDPR-K/UK Children's Code, India DPDP), DPA with Groq, retention policy sign-off. |
| B5 | Licensing | WebGazer is GPLv3 with separate commercial terms. | Loaded at runtime from its own distribution; not bundled. | Legal review before any commercial deployment. |
| B6 | Lexi | LLM output can be wrong or ignore instructions; no output moderation layer. | Strict system prompt, short replies, disclosure, no child data sent, rate limits. | Live red-team test with a real key; consider moderation API. |
| B7 | Security | No independent penetration test; no MFA; registration reveals whether an email exists (409). | Rate limits, audit log, timing-equalised login. | Pen test; email verification flow. |
| B8 | Ops | No backups, monitoring, alerting or TLS configured in this repo; rate-limit state is per process. | Health/readiness probes; logs with request ids. | Managed PostgreSQL with backups + restore drill; shared rate-limit store (Redis) for multiple replicas. |
| B9 | Accessibility | Automated axe checks (WCAG 2.1 A/AA rules) on key pages only. | Keyboard flows, labels, focus management, reduced motion. | Manual audit with screen readers and children's usability testing. |
| B10 | Localization | Tamil strings added in this pass are machine-authored. | Catalog coverage test. | Native-speaker review; Tamil game content does not exist (honestly marked unavailable). |
| B11 | Data | Legacy SQLite dev databases keep FKs without cascade and some nullable columns. | Explicit-order deletion. | Recreate dev databases from migrations when convenient. |
| B14 | Screening | Parents may over-interpret a future percentage. No eligible model exists today. | Strict eligibility gate; calibrated output only; bands only from specialist-approved thresholds; non-diagnostic copy with next steps (EN/TA). | Real labelled data per `ai-ml-validation.md` §8.5; specialist review of all screening copy; usability testing with parents. |
| B15 | Screening | A fabricated or mislabelled model card could be installed by an operator. | Artifact-embedded provenance cross-checked with the card; SHA-256; reviewer references required. | Signed artifacts and a documented model-release approval process. |
| B16 | Research predictor | A synthetic-data score shown on a real child's results could be mistaken for a dyslexia probability, or research mode could be left on for real families. | Off by default; refused in production; separate page and table; never on the parent card; "NOT a real-child dyslexia probability" label (EN/TA); access limited to owner or granted educator. | Keep research mode to development/test servers; specialist review of the research page copy if it is ever shown to non-developers. |
| B17 | Research predictor | Pickle artifacts execute code when loaded. | Committed, locally generated artifact; SHA-256 checked before unpickling; runtime version check; no upload endpoint. | Signed artifacts or a non-executable format (e.g. skops/ONNX) before any distribution. |
| B13 | Dependencies | Optional offline speech-ML set (`requirements-speech-ml.txt`) has advisories: transformers 4.46.3 (fixes in 4.51–5.10), datasets 3.2.0, accelerate 1.3.0 (no fix), fsspec, setuptools. Not installed in the API image. | Only used offline by operators on trusted data. | Migrate fine-tuning code to transformers 5.x and re-run `tests/ml/speech` before using it on real data. |
| B12 | Gaze | Real camera behaviour not verified in this pass (headless only). | Consent, SRI, coordinates-only. | Manual test on target devices; validate CSP with real model downloads. |
