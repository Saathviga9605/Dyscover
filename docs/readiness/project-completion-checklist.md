# Project Completion Checklist

Release pass of 2026-10-21. Every ✅ below was re-run on the final working tree; commands and counts are in `final-integration-report.md` §8.

## Release gate (research/educational demo)

| Gate | Status | Evidence |
|---|---|---|
| Installable and startable from documented instructions | ✅ | Clean venv created with the documented PowerShell commands; `pip check` clean; `README.md` Quick Start |
| Backend and frontend build and run | ✅ | Backend 431 passed / 1 skipped; `tsc` 0 errors; ESLint 0 errors; Vitest 160 passed; `npm run build` OK |
| All eight games work against the real backend | ✅ (automated) | Playwright: 5 visual games and 3 speech games (speech recognition stubbed at the browser API) |
| Authentication, authorization, sharing, privacy | ✅ | Backend security/IDOR/privacy tests; Playwright auth, sharing, export and deletion journeys |
| Lexi configured / unconfigured | ✅ | Live Groq test passed with the configured key; Playwright uses the echo provider; the production smoke stack reports `not_configured` gracefully |
| Synthetic research model loads and scores real game-derived features | ✅ | `python -m app.ml.screening.verify`; backend and Playwright research tests |
| Research UI shows the actual output with the correct interpretation | ✅ | Playwright: the rendered percentage equals the API response; "NOT a real-child dyslexia probability" |
| Parent screening shows no unsupported probability | ✅ | Playwright and backend: `no_eligible_model`, no `%` |
| Synthetic models cannot enter the production registry | ✅ | Registry tests; `verify` against the production registry lists the refusal reasons |
| Migrations and privacy operations on PostgreSQL | ✅ | Full suite on PostgreSQL 16 (344 passed); 0003→0004 upgrade with data, no loss; downgrade/upgrade; `pg_dump`/`pg_restore`; zero schema diff; no orphans after account deletion |
| Reproducible Python environment | ✅ | Root cause fixed (`include-system-site-packages = true`); every package resolves from `.venv` |
| Fresh automated results recorded | ✅ | `final-integration-report.md` §8 |
| Deployment, configuration, backup, recovery, rollback docs | ✅ | `docs/deployment.md`; backup/restore commands verified on the Compose stack |
| No secrets or child data added to version control | ✅ | `.env` ignored; the JS bundle scan found 0 secrets; only synthetic artifacts were added |
| Git status reviewed; nothing committed or pushed | ✅ | See the report |

## Required before release

None outstanding.

## Required before external/public access

| Item | Next action / owner |
|---|---|
| Real host, DNS and TLS certificate | Operator: provision and follow `docs/deployment.md` §1–5 |
| Off-host, encrypted, scheduled backups plus a restore drill on the real host | Operator |
| Monitoring and alerting; a shared rate-limit store for multiple replicas | Operator (`risk-register.md` B8) |
| Legal and privacy review (COPPA / GDPR-K / UK Children's Code / India DPDP), a DPA with Groq, a retention policy | Project owner with qualified counsel (B4, B5) |
| Independent penetration test, MFA, email verification | Project owner (B7) |
| Specialist review of parent/educator copy; native-speaker Tamil review | Project owner (B1, B10) |
| Manual screen-reader audit and usability testing with children | Project owner (B9) |

## External integration requiring credentials or hardware

| Item | Status |
|---|---|
| Real microphone (Web Speech API) on target devices | Not verified; automated tests stub the browser recognition API |
| Real camera / WebGazer on target devices | Not verified; headless only (B12) |
| Whisper speech fine-tuning on children's read speech | Blocked: no licensed child-speech corpus (`ai-ml-validation.md` §6) |

## Future clinical research (not an engineering task)

- Labelled real-child data, ethics approval, external validation, specialist threshold review and a regulatory assessment (`ai-ml-validation.md` §5, §8.5). Until then the clinical screening registry correctly stays empty.

## Optional enhancements (not blockers)

- Split the frontend bundle (Vite chunk-size warning).
- Migrate the optional speech-ML stack to transformers 5.x (B13).
- Use a non-executable model format (skops/ONNX) or signed artifacts (B17).
- Clean up the 52 existing ESLint warnings.
