# Dyscover — Invention Disclosure (Draft for Counsel)

Updated 2026-10-21. Internal draft for review by a qualified patent attorney. It records what the code does and the evidence for it. It makes **no** assertion of novelty, patentability or freedom to operate — none of those has been assessed, and no prior-art search has been performed.

## 0. Time-critical issue for counsel

The repository `github.com/Saathviga9605/Dyscover` is **publicly accessible** (unauthenticated HTTP 200, checked 2026-10-21), and git history shows pushes since at least the first commits of this project. Public availability of source code and documentation may already constitute a public disclosure of the mechanisms below. In absolute-novelty jurisdictions (e.g. EPO; India) this can bar patent protection; in the US a 12-month grace period runs from the first disclosure. Counsel should establish the date the repository first became public and advise before any further publication. This document itself should not be published.

## 1. Working title

Consent-gated multimodal observation platform for early-literacy activities, with server-verified trial outcomes, modality-availability-aware features, and separation of assessment evidence from practice.

## 2. Technical field

Educational technology; web-based capture of interaction, gaze-estimate and speech-recognition signals from children's literacy games; privacy-preserving telemetry; rule-based personalization.

## 3. Mechanisms implemented (facts, with evidence)

| # | Mechanism | Where | Evidence |
|---|---|---|---|
| M1 | **Server-side re-scoring of client-generated game trials.** The browser generates stimuli and submits stimulus, expected and actual response; the server recomputes correctness/score for five game types with rules mirrored from the client, keeps the client's claim separately when they disagree, and stores trials without a response as *unscored* rather than wrong. | `backend/app/assessments/scoring.py`, `routes.py` | `tests/test_assessment_integrity.py` |
| M2 | **Modality-availability-aware features.** Every extracted feature carries `available`/`status`; unrecorded gaze/speech is `null` and unavailable, never 0; models append missingness indicators; recognition failures and silence are unscored instead of counted as reading errors. | `backend/app/ml/features.py`, `models.py`; `frontend/src/games/speech/speechDefinitions.ts` | ML and e2e tests |
| M3 | **Separation of assessment evidence from practice.** Remedial practice sessions/events live in separate tables and APIs and are never used as assessment evidence. | `backend/app/models.py`, `app/remedial` | `tests/test_remedial.py` |
| M4 | **Evidence-gated, non-clinical personalization.** Deterministic rules with minimum-evidence thresholds; "insufficient evidence" is an explicit output; categories are relative and non-clinical. | `backend/app/personalization` | `tests/test_personalization.py` |
| M5 | **Synthetic-data research pipeline with deployment gate.** Seeded simulator with nine profiles, subject-level splits, permutation probe, SHA-256-verified artifacts flagged `synthetic`/`clinical_use: prohibited`, and a production registry that refuses them. | `backend/app/ml/synthetic` | `tests/test_synthetic_ml.py`, `evidence/synthetic-multiseed.json` |
| M6 | **Owner-granted, revocable educator access to aggregated summaries only.** | `backend/app/children`, `app/educator`, `app/access.py` | `tests/test_educator_access.py` |
| M7 | **Language as structured metadata with honest availability.** Language/locale/content version recorded on assessments, games and trials; activities without curated content in a language are reported unavailable rather than auto-translated. | `backend/app/l10n.py`, `frontend/src/l10n` | `tests/test_l10n.py` |
| M8 | **Lexi assistant boundary.** Server-only system prompt with non-diagnosis rules, contact-detail redaction before the provider call, write-after-success persistence with idempotency keys. | `backend/app/chat` | `tests/test_chat.py` |

Correction to the previous draft: consent for gaze and speech is held in the browser (local storage) and gates capture in the client; it is **not** persisted or queryable on the server. Leakage prevention is a subject-level random split plus a permutation probe — not a formal guarantee.

## 4. What is not implemented (do not describe as existing)

- Any validated prediction of dyslexia or reading difficulty (prediction endpoint returns `unavailable`).
- Server-issued stimuli; server-side consent records; Tamil content for speech games; personalization for speech games.
- Speech-model fine-tuning results (pipeline exists; no experiment run — see `ai-ml-validation.md` §6).

## 5. Third-party components relevant to any claim

WebGazer.js 3.5.3 (GPLv3 / separate commercial licence) for gaze estimation; browser Web Speech API; optional OpenAI Whisper weights (MIT) via Hugging Face/faster-whisper; Groq-hosted LLM for Lexi. Claims should not read on these components' own functionality.

## 6. Questions for counsel

1. Effect of the public GitHub repository (§0) on each mechanism and jurisdiction.
2. Whether M1/M2 (server re-scoring with unscored states; availability-aware features) merit a prior-art search, and in which classes.
3. Inventorship (not determined here).
4. Licensing implications of WebGazer (GPLv3) for distribution and for any patent licensing strategy.

## 7. Supporting records

Git history; `docs/readiness/final-integration-report.md` (commands, test counts); `docs/readiness/evidence/`.
