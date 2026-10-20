# Dyscover Invention Disclosure Draft

**Date:** 2026-10-20  
**Status:** DRAFT — For internal review only  
**Confidentiality:** Do not distribute externally without legal review

---

## 1. Title

**Multimodal Adaptive Learning Platform with Research-Grade Telemetry Isolation and Synthetic Validation Pipeline**

---

## 2. Inventors

[To be completed with legal counsel]

---

## 3. Technical Field

Educational technology, adaptive learning systems, multimodal human-computer interaction, machine learning for behavioral phenotyping, privacy-preserving telemetry architectures.

---

## 4. Problem Statement

Existing dyslexia screening tools suffer from several limitations:
1. **Clinical conflation**: Screening tools often present probabilistic outputs as diagnostic indicators
2. **Telemetry contamination**: Practice/learning data mixes with assessment evidence
3. **Modality opacity**: Gaze/speech/behavioral data quality not explicitly reported
4. **Validation gap**: ML models trained on synthetic/real data without strict isolation
5. **Privacy gaps**: Raw audio/video often stored; consent flows incomplete
6. **Multilingual neglect**: Non-English assessment content poorly supported

---

## 5. Novel Technical Contributions

### 5.1 Strict Assessment/Practice Data Isolation

**Mechanism:** Separate database tables (`assessment_sessions` vs `practice_sessions`), distinct event schemas with mandatory `mode="practice"` field, separate API endpoints (`/api/assessments/*` vs `/api/remedial/*`), and evidence gates that reject practice data from assessment feature extraction.

**Key Innovation:** Canonical event contract shared between assessment and practice, but `mode` field and separate persistence ensure practice data can NEVER be mistaken for assessment evidence. Feature extraction pipeline explicitly filters by `mode="assessment"`.

### 5.2 Modality-Availability-Aware Feature Extraction

**Mechanism:** Each feature carries explicit `available: boolean` and `quality: enum` fields. Features report `null` with `available=false` when modality data missing, NOT zero. Quality metadata includes sample counts, calibration status, calibration completion events, ASR availability flags.

**Key Innovation:** Downstream consumers (personalization, ML, dashboards) can distinguish "child performed poorly" from "modality unavailable" — preventing false negative interpretations.

### 5.3 Synthetic Data Pipeline with Provenance & Leakage Prevention

**Mechanism:**
- Deterministic simulator with 9 documented interaction profiles
- Subject-level GroupKFold splitting (no subject leakage)
- SHA256 checksum over deterministic row contents (excl. timestamps)
- Purity verification: `ensure_synthetic_purity()` rejects mixed datasets
- Artifact integrity: SHA256 of pickled model + metadata validation on load
- Registry gatekeeper: `register_model()` rejects `synthetic=True` models

**Key Innovation:** End-to-end synthetic pipeline that is provably isolated from real data, with mathematical leakage prevention (subject-level splits) and cryptographic integrity verification.

### 5.4 Consent-Gated Multimodal Capture

**Mechanism:**
- Gaze: Explicit WebGazer consent card → camera permission → calibration → calibrated/uncalibrated/low-quality tracking states
- Speech: Browser SpeechRecognition + optional local Whisper → consent card with microphone skip option → audio never persisted by default
- Both: Consent state persisted per session, granular per-modality

**Key Innovation:** Consent as first-class persisted state, not UI-only. Quality states (unavailable, uncalibrated, low-quality, valid) distinguish hardware/consent failures from behavioral patterns.

### 5.5 Language-Aware Assessment Architecture

**Mechanism:**
- Assessment metadata: `language`, `locale`, `content_version` persisted at session/game/trial level
- Game registry validates game-language pairs (e.g., Tamil only for mirror-match)
- Speech tasks filtered by language support
- Locale derivation: `ta → ta-IN`, `en → en-US` canonicalized server-side

**Key Innovation:** Language as structured metadata at every telemetry level, not just UI translation. Server canonicalizes locale/content_version from language.

### 5.6 Rule-Based Personalization with Evidence Gates

**Mechanism:**
- Domain evidence: `evidence_trials` count, `accuracy`, `quality` (sufficient/insufficient)
- Minimum evidence threshold: ≥3 trials for `sufficient`
- Categories: `relative_strength`, `developing`, `practice_opportunity` — NO clinical labels
- Difficulty adaptation: ±1 level bounded, window-based (recent 5 trials), hysteresis
- Insufficient evidence → explicit `insufficient_evidence` state, NOT default recommendations

**Key Innovation:** Personalization driven by explicit evidence thresholds with "insufficient evidence" as a first-class output, not a fallback.

### 5.7 Educator Authorization with Revocation

**Mechanism:**
- `EducatorLearnerAssignment` table with `status` (active/revoked), `revoked_at`, `revocation_reason`
- All educator endpoints check active assignment
- Revocation immediate, audit logged
- Educator dashboard aggregates only authorized learners

**Key Innovation:** Fine-grained, auditable, revocable access control at the learner level with server-side enforcement on every request.

---

## 6. Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React/TS)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Games    │ │ Speech   │ │ Gaze     │ │ Dashboards       │  │
│  │ Engine   │ │ Runner   │ │ Tracker  │ │ (Parent/Educator)│  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
└───────┼─────────────┼────────────┼────────────────┼────────────┘
        │             │            │                │
        ▼             ▼            ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Auth     │ │ Assess-  │ │ Remedial │ │ ML/Synthetic     │  │
│  │ (JWT)    │ │ ment API │ │ API      │ │ Pipeline         │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
└───────┼─────────────┼────────────┼────────────────┼────────────┘
        │             │            │                │
        ▼             ▼            ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL / SQLite                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Users/   │ │ Assess-  │ │ Practice │ │ ML Artifacts     │  │
│  │ Children │ │ ment Data│ │ Data     │ │ (Synthetic Only) │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Prior Art Differentiation

| Feature | Dyscover | Typical Screening Tools |
|---------|----------|------------------------|
| Practice/Assessment isolation | Separate tables, schemas, APIs | Often mixed |
| Modality availability in features | Explicit `available`/`quality` per feature | Implicit/assumed |
| Synthetic validation pipeline | Subject-level splits, SHA256, gatekeeper | Rarely documented |
| Consent as persisted state | Per-modality, granular | Often UI-only |
| Language as structured metadata | Session/game/trial level | Usually UI only |
| Personalization evidence gates | Minimum trials, explicit insufficient | Often heuristic |
| Educator revocation | Immediate, audited | Often coarse |

---

## 8. Potential Claims (For Patent Counsel Review)

### Claim Categories:
1. **System Claims**: Multimodal adaptive learning platform with isolated assessment/practice telemetry
2. **Method Claims**: Consent-gated gaze/speech capture with quality-state persistence
3. **Method Claims**: Synthetic data generation with subject-level leakage prevention and cryptographic integrity
4. **Method Claims**: Rule-based personalization with explicit evidence thresholds and insufficient-evidence state
5. **System Claims**: Language-canonicalized assessment architecture with per-telemetry metadata
6. **Method Claims**: Educator authorization with immediate revocation and audit trail

### Key Differentiators to Emphasize:
- **Assessment/Practice isolation at schema level** (not just logical)
- **Modality availability as first-class feature property** (not implicit)
- **Synthetic pipeline with mathematical leakage prevention** (subject-level GroupKFold)
- **Consent as queryable persisted state** (not ephemeral UI)
- **Clinical-use gatekeeper at registry level** (enforced in code)

---

## 9. Development Evidence

| Component | Files | Tests | Status |
|-----------|-------|-------|--------|
| Auth/JWT | `backend/app/auth/*` | 12 tests | ✅ |
| Assessment API | `backend/app/main.py` | 15 tests | ✅ |
| Games (8) | `frontend/src/games/definitions/*` | 40+ tests | ✅ |
| Game Engine | `frontend/src/games/engine/*` | 12 tests | ✅ |
| Speech Pipeline | `backend/app/speech/*`, `frontend/src/speech/*` | 18 tests | ✅ |
| Gaze Pipeline | `backend/app/gaze/*`, `frontend/src/gaze/*` | 31 tests | ✅ |
| Synthetic ML | `backend/app/ml/synthetic/*` | 17 tests | ✅ |
| Personalization | `backend/app/personalization/*` | 24 tests | ✅ |
| Remedial | `backend/app/remedial/*` | 20 tests | ✅ |
| Educator Access | `backend/app/main.py` | 3 tests | ✅ |
| Internationalization | `frontend/src/l10n/*` | 20 tests | ✅ |

---

## 10. Known Limitations (For Disclosure)

1. **Transformers install on Windows** blocks speech ML tests (4 tests) — long path issue
2. **No clinical validation** — synthetic pipeline only
3. **WCAG audit pending** — accessibility not yet verified
4. **PWA not implemented** — offline support incomplete
5. **Tamil speech games not implemented** — only mirror-match supports Tamil

---

## 11. Next Steps for Patent Filing

1. **Legal review** of this disclosure with qualified patent attorney
2. **Claim drafting** focusing on schema-level isolation, modality availability features, synthetic pipeline integrity
3. **Prior art search** for: multimodal educational telemetry, synthetic ML validation, consent-gated capture
4. **Provisional filing** decision within 12 months of first public disclosure
5. **International filing strategy** (PCT vs. national) based on market analysis

---

## 12. Confidentiality Notice

This document contains potentially patentable technical details. Do not distribute externally, publish, or present at conferences without explicit written authorization from legal counsel. All development records (git history, test results, architecture decisions) should be preserved for potential patent prosecution.

---

**End of Draft**