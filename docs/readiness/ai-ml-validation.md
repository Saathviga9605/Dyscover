# AI/ML Validation Report

Updated 2026-10-21. Evidence file: `docs/readiness/evidence/synthetic-multiseed.json` (produced by `python -m app.ml.synthetic.experiment --seeds 1 2 3 4 5 --subjects 60`).

**Bottom line:** Dyscover has no model validated on real children's data. All trained models are research artifacts fitted to **synthetic, simulator-defined** interaction profiles. Predictive inference in the product is disabled (`POST /api/ml/predict/session/{id}` always returns `status: unavailable`), and the production model registry refuses models flagged `synthetic`. Nothing in this report is evidence of dyslexia detection accuracy.

## 1. What runs in the product today

| Capability | Status | Evidence |
|---|---|---|
| Per-session feature extraction from persisted trials/events/gaze/speech (40 registered features, schema 1.0) | Implemented and tested | `app/ml/features.py`, `tests/test_api.py::test_end_to_end_telemetry_reaches_feature_extraction` |
| Missing modalities | Reported as `value: null, available: false` — never zero | `features.py` `_append_gaze_features/_append_speech_features`; modality summary returns `null` coverage when nothing was recorded |
| Descriptive "screening profile" (observations, data quality, limitations) | Implemented; descriptive only | `app/ml/profile.py` |
| Reading-difficulty screening percentage | Pipeline, gate, API and UI implemented; **no eligible model exists**, so no percentage is shown | §8; `GET /api/screening/children/{id}` |
| Synthetic research predictor | Trained, saved and run on real stored game results through a research-only API and page; off by default and refused in production; its output is a synthetic-target probability, **not** a real-child dyslexia probability | §9; `POST /api/screening/research/children/{id}/assessments/{aid}/predict` |
| Personalization rules | Deterministic, rule-based, uses scored visual-game trials only | `tests/test_personalization.py` |

## 2. Synthetic dataset

- Generator: `app/ml/synthetic` (seeded, checksummed). Each simulated subject is assigned one of 9 simulator profiles (`taxonomy.py`): consistent_responses, variable_response_timing, high_error_frequency, repeated_symbol_confusions, reduced_reading_response_coverage, attention_variability, working_memory_task_difficulty, mixed_interaction_profile, and insufficient_observations (excluded from training).
- **Meaning of the labels:** a label is the parameter set the simulator used to generate that subject. Labels are *not* clinical categories and none corresponds to "dyslexic"/"not dyslexic".
- Modality availability is simulated (default 70% of sessions have optional gaze/speech); unavailable modalities stay missing.

## 3. Method

- **Split:** subject-level random split (70/15/15) — all sessions of a subject are in one partition (`app/ml/datasets.py::subject_level_split`). Not stratified by class, so a partition may lack a class.
- **Preprocessing:** median imputation **with missingness indicators** (added in this pass so "not recorded" is not conflated with a typical value), standard scaling for logistic regression; fitted inside the scikit-learn pipeline on training rows only.
- **Estimators:** stratified `DummyClassifier` (baseline), logistic regression, random forest (balanced), gradient boosting.
- **Seeds:** 1–5, 60 simulated subjects per seed (108 eligible sessions → 38 train / 8 validation / 8 test subjects).
- **Leakage probes:** (a) random forest retrained with shuffled training labels; (b) random-forest feature importances inspected for any single dominant feature.

## 4. Results (held-out test subjects, 5 seeds)

8 eligible classes; chance level = 0.125.

| Model | Accuracy mean ± SD (min–max) | Macro-F1 mean ± SD (min–max) |
|---|---|---|
| Dummy (stratified) | 0.150 ± 0.034 (0.125–0.188) | 0.118 ± 0.026 (0.086–0.146) |
| Logistic regression | 0.388 ± 0.136 (0.250–0.563) | 0.317 ± 0.061 (0.225–0.396) |
| Random forest | 0.438 ± 0.171 (0.250–0.688) | 0.381 ± 0.090 (0.300–0.532) |
| Gradient boosting | 0.525 ± 0.169 (0.313–0.688) | 0.434 ± 0.077 (0.337–0.517) |
| Random forest, **shuffled labels** | 0.050 ± 0.052 (0.000–0.125) | 0.034 ± 0.035 |

Interpretation:
- Learned models exceed the dummy baseline on every seed: the simulator's profiles leave a learnable signal, mainly in reaction-time and hesitation features (top importances each seed: mean/median reaction time, mean hesitation time; none above ~0.14).
- The shuffled-label probe collapses to (below) chance → no evidence of label leakage through the split or the features.
- **The test set is tiny (8 subjects ≈ 16 sessions per seed)**, so seed-to-seed spread is ±0.17 accuracy; single-seed numbers in older documents should not be quoted.
- These numbers measure **recovery of simulator parameters**. Because the simulator was written by the developers, good separability partly reflects how distinct the simulated profiles were made, not anything about children.

## 5. Requirements before any real-world predictive use

1. Ethics approval and verifiable parental consent for collecting assessment data for model development.
2. A real dataset with reference labels from a qualified, standardised assessment performed independently of Dyscover (labels never derived from Dyscover's own outputs), with documented age, language, and site distribution.
3. Pre-registered evaluation: subject-level splits, external test site, sensitivity/specificity with confidence intervals, calibration, subgroup analysis (age, language incl. Tamil, device), and comparison to existing screeners.
4. Specialist review of intended use, thresholds, and how results are communicated to parents and educators.
5. Regulatory assessment (a tool that claims to detect a condition may be a medical device in some jurisdictions).
6. Model card and monitoring plan; only then lift the `predict` block, behind an explicit configuration flag.

## 6. Speech ML

- Infrastructure (manifest validation, speaker-disjoint splits, Whisper fine-tuning/evaluation with WER/CER, CLI) is implemented and its tests pass on this machine: `pytest tests/ml/speech` → 85 passed (incl. 2 audio-decoding tests previously marked xfail on Windows, now passing and un-marked).
- **No fine-tuning experiment was run.** Blocker: no appropriately licensed corpus of *children's read speech* with speaker IDs is available in this environment, and no Whisper weights are cached. Fine-tuning on adult audiobook speech would not answer the question that matters (child reading). No WER/CER results are claimed.
- Game speech recognition uses the browser's Web Speech API; its accuracy for children and for Tamil is unknown and unmeasured. Recognition failures are recorded as unscored, separately from reading performance.

## 7. Artifact handling

- Artifacts carry `synthetic: true`, `clinical_use: prohibited`, feature list, schema version and SHA-256; loading verifies all of them (`load_synthetic_model`), rejects path components in artifact names, and the production registry rejects synthetic models.
- Pickle artifacts execute code on load; they are operator-produced only. There is no endpoint that accepts model uploads.

## 8. Reading-difficulty screening pipeline (added 2026-10-21)

### 8.1 Intended use and target

- **Intended use:** help parents and educators decide whether to *seek* a professional reading assessment. Not diagnosis, not treatment selection, not a substitute for professional assessment.
- **Target (`elevated_reading_difficulty_risk_v1`):** positive when a standardised reading/phonological assessment, administered independently of Dyscover and interpreted by a qualified specialist, recommended further assessment or reading support. This deliberately does not equal "dyslexia": reading difficulties have many causes, and dyslexia is a diagnosis made by professionals.

### 8.2 Data audit (result: no usable data)

| Question | Finding |
|---|---|
| Labelled real-child data in the repository? | **None.** `dyscover.db` contains game telemetry without any reference-assessment labels (and most rows are leftovers from earlier automated test runs). |
| Synthetic data | Simulator profiles; labels are simulator settings, not clinical ground truth. Used only for software tests. |
| Public datasets | None downloaded. Any dataset must match the data contract below *and* Dyscover's own features — published dyslexia datasets use different tasks, so they cannot simply be reused. |

Consequently **no model is eligible** and the product shows no percentage (verified in the browser e2e test).

### 8.3 What was built

| Component | Location |
|---|---|
| Target definition and versioned feature schema (`screening-1.0`, 15 rate/timing features; identifiers, counts that scale with session length, and label-like names are rejected by `assert_schema_is_leak_free`) | `app/ml/screening/schema.py` |
| Validation of inputs (range/type checks; missing stays `None`, never 0) | `schema.py::validate_features` |
| Training: participant-grouped stratified splits, preprocessing inside the pipeline (median + missingness indicators), model selection on validation ROC-AUC, sigmoid calibration on validation only when ≥60 participants and ≥15 per class, held-out evaluation with ROC-AUC, PR-AUC, Brier, sensitivity, specificity, PPV, NPV, participant-level bootstrap 95% CIs, calibration bins, dummy baseline, and a reliability flag (<100 test participants or <30 positives ⇒ "not evidence") | `app/ml/screening/training.py` |
| Thresholds: training only *proposes* a candidate (sensitivity ≥ 0.85 on validation) marked `requires_specialist_approval`; only thresholds a reviewer writes into `validation.approved_thresholds` are ever shown as bands | `training.py`, `service.py::_band` |
| Artifact with embedded provenance (`training_data`, `output_type`) + model card with SHA-256 | `model.py`, `training.py` |
| Registry + eligibility gate (target, schema version, real training data in card **and** artifact, calibrated output, reliable sample, external validation / specialist review / ethics references, defined ages and languages, intact artifact) | `app/ml/screening/registry.py` |
| Inference service: owner/granted-educator access, latest *completed* assessment only, population and minimum-observation checks, explicit statuses, one stored result per assessment × model version, logs without features | `app/ml/screening/service.py`, `GET /api/screening/children/{id}` |
| Admin-only synthetic research demo, off by default (`RESEARCH_DEMO_ENABLED`), labelled "Synthetic-data research demonstration — not a real-child risk estimate", never stored | `routes.py` |
| Parent "Dyslexia risk screening" card (EN/TA) | `frontend/src/app/ScreeningCard.tsx` |

### 8.4 Synthetic engineering run (NOT performance evidence)

> Superseded by §9. The session-level run below used single-game rows that lack the domain features; it is kept for history.

`python -m app.ml.screening.training --synthetic-demo --subjects 300 --output <dir>`: 534 sessions / 267 simulated subjects (159 train, 54 validation, 54 test). The validation set was too small to calibrate, so the output is labelled `research_score`; test ROC-AUC 0.85 is flagged `reliable_sample_size: false`. These numbers reflect simulator settings chosen by developers and say nothing about children.

### 8.5 Data contract for a real model

1. **CSV**: `participant_id,label,<screening-1.0 feature columns>`; one or more rows per child, each row = one *completed* Dyscover session collected before the reference assessment (no post-assessment information).
2. **Labels**: from an independent standardised assessment within a defined window (e.g. ≤ 3 months), interpreted by a qualified specialist; label rule documented.
3. **Provenance JSON** (required by the trainer): `source`, `license`, `consent_and_ethics`, `label_definition`, `label_method`, `population` (ages, languages incl. English/Tamil coverage, schools/regions, inclusion/exclusion criteria).
4. **Size**: at minimum enough for ≥100 held-out participants and ≥30 held-out positives, and ≥60 validation participants for calibration — more for subgroup (age, language) analysis.
5. **After training**: an independent reviewer fills in `validation.external_validation_reference`, `specialist_review_reference`, `ethics_approval_reference`, `intended_population`, `min_scored_trials`, and any `approved_thresholds`; the model directory is placed under `SCREENING_MODEL_DIR`.

### 8.6 Operations

- **Versioning:** results are stored per (assessment, model_id, version); a new version adds a row, history is kept until the child is deleted.
- **Monitoring (to implement with real data):** score distribution drift per month, proportion of each status, language/age mix vs. the validated population, and periodic follow-up of outcomes where consent allows.
- **Disable/rollback:** remove or rename the model directory (the API immediately falls back to `no_eligible_model`); stored results stay attributable to their version. Disable if drift exceeds agreed limits, if a safety/fairness issue is reported, or if the validated population no longer matches users.

## 9. Synthetic research predictor (added 2026-10-21)

**What it is:** a trained, saved, loadable model that runs on a child's *real stored game results* and returns its real output through a research-only API and page. **What it is not:** a dyslexia screening model. It was trained only on simulated data, and its labels are simulator settings chosen by developers.

### 9.1 Dataset and label-generation rule

- **Generator:** `app/ml/screening/research_data.py` (`generate_research_dataset`, dataset version `screening-synthetic-assessments-1.0`). It reuses the existing simulator's per-trial rules (`app/ml/synthetic/simulator.py::simulate_trial_sequence`, profile parameters in `taxonomy.py`) and its gaze simulation.
- **Why a new generator:** the original synthetic dataset (`artifacts/synthetic/dataset.json`) has one row per *single-game* session, with 5 trials and one domain. It never contains the four `domain_*_accuracy` features of `screening-1.0`, so it cannot match a real assessment. The new generator composes each synthetic assessment exactly like the app's visual run: letter-detective 5, mirror-match 5, word-flash 5, sequence-quest 4 and word-maze 3, giving 22 trials across 4 domains. The features use the same formulas as `app/ml/features.py::extract_session_features`.
- **Configuration used:** seed 42, 800 participants × 2 assessments = 1,600 rows, gaze available in 30% of assessments, data checksum `d11cdcac…58bd2d7`.
- **Participants:** neutral IDs (`synthetic-participant-00000`). Each participant is assigned one of the 8 trainable profiles, cycled so they are balanced.
- **Label rule:** label = 1 if the profile ∈ {high_error_frequency, repeated_symbol_confusions, reduced_reading_response_coverage, working_memory_task_difficulty}; otherwise 0 (attention_variability, consistent_responses, mixed_interaction_profile, variable_response_timing). Prevalence is 50% by construction.
- **Important:** the label is a deterministic function of the same simulator profile that generates every feature (accuracy range, reaction-time mean and variance, hesitation). The model therefore learns to *recover the simulator's settings*. High scores below are expected and **are not evidence about children**.
- **Missing data:** speech features are always missing, because the visual run records no read-aloud speech. Gaze features are missing in about 70% of rows. Missing values stay `None`, never 0. `completion_rate` is always 1.0, because the app stores only answered trials, so it carries no information.
- **Data handling (`prepare_rows`):** rows with an invalid label, no participant ID, missing required features or out-of-range values are excluded and counted. Exact duplicates are dropped. Participants with contradictory labels are excluded entirely. In this run, all of these counts were 0.

### 9.2 Training procedure

`python -m app.ml.screening.training --synthetic-demo --version 1.0.0 --output artifacts/screening-synthetic/dyscover-research-synthetic` (takes about 15 s on the development machine):

- **Split:** `StratifiedGroupKFold` by participant: 1/5 test, then 1/4 of the remainder for validation, giving train 480 / validation 160 / test 160 participants. A participant never appears in two partitions, and this is asserted.
- **Leakage check (training partition):** the schema name check, plus a univariate ROC-AUC per feature. Any feature with AUC ≥ 0.98 aborts training with `LeakageError`.
  - In this run, the maximum was `overall_accuracy` at 0.807.
  - A test confirms the check fires when a label-derived value is injected.
- **Preprocessing:** median imputation with missingness indicators (plus scaling for logistic regression), inside the pipeline and fitted on train only. A test confirms the imputer statistics equal the training-partition medians.
- **Candidates:** prior (dummy) baseline; logistic regression with C ∈ {0.1, 1, 10}; random forest with depth ∈ {4, 8} and 300 trees; gradient boosting with depth ∈ {2, 3} and 150 trees.
- **Selection criterion:** highest *validation* ROC-AUC among the non-baseline candidates. The test set is not used for selection.

| Candidate | Validation ROC-AUC |
|---|---|
| dummy_prior | 0.500 |
| logistic_regression C=0.1 / 1 / 10 | 0.818 / 0.818 / 0.818 |
| random_forest depth 4 / 8 | 0.958 / 0.989 |
| gradient_boosting depth 2 / **3 (selected)** | 0.988 / **0.992** |

- **Calibration:** sigmoid, on validation (`CalibratedClassifierCV(FrozenEstimator)`). It was fitted because validation had 160 participants and at least 15 rows per class, so `output_type = calibrated_probability`. This means calibrated **for the synthetic target only**.
- **Threshold:** the candidate threshold 0.941 is chosen as the point where validation sensitivity ≥ 0.85, marked `requires_specialist_approval`. It is used only to report sensitivity and specificity. No band is shown anywhere.

### 9.3 Results (synthetic; measure recovery of simulator settings only)

| Partition | Rows / participants | ROC-AUC | PR-AUC | Brier | Sens. | Spec. | PPV | NPV | Confusion at 0.941 (TP/TN/FP/FN) |
|---|---|---|---|---|---|---|---|---|---|
| Train | 960 / 480 | 1.000 | 1.000 | 0.002 | 0.892 | 1.000 | 1.000 | 0.905 | — |
| Validation (also used for calibration, so optimistic) | 320 / 160 | 0.992 | 0.991 | 0.033 | 0.851 | 0.982 | 0.978 | 0.876 | 131 / 163 / 3 / 23 |
| **Test (held out)** | 320 / 160 | **0.992** (95% CI 0.984–0.998) | 0.993 (0.985–0.998) | 0.032 (0.018–0.050) | 0.874 (0.815–0.929) | 0.979 (0.953–1.000) | 0.981 (0.954–1.000) | 0.867 (0.800–0.927) | 152 / 143 / 3 / 22 |
| Dummy baseline (test) | 320 / 160 | 0.500 | 0.544 | 0.251 | — | — | — | — | — |

- Confidence intervals come from a participant-level bootstrap with 1,000 resamples.
- The training metrics (AUC 1.0) show that gradient boosting fits the training simulator data perfectly.
- The test metrics are near-perfect because the label and the features come from the same profile parameters (§9.1). **None of these numbers describe dyslexia detection.**

### 9.4 Artifact

`backend/artifacts/screening-synthetic/dyscover-research-synthetic/`:
- `model.pkl`: the `ScreeningModel` containing the calibrated pipeline, the ordered feature names, schema `screening-1.0`, target `synthetic_reading_difficulty_profile_v1`, `training_data: synthetic` and the output type.
- `model_card.json`: designation `synthetic_research`, target definition, dataset metadata and checksum, seed, runtime (Python 3.13.14, numpy 2.2.2, scikit-learn 1.6.1, matching `requirements.txt`), training configuration, leakage report, training-feature reference (median and 1st–99th percentiles), model selection, all metrics, input requirements, and SHA-256 `16d52b48fa9765f36dabd8bf3bf28da20a4220630885a594b208a6ef732f157d`.

How loading is protected:
- The checksum is verified before the pickle is read.
- The scikit-learn major.minor version must match the runtime.
- The object must be a `ScreeningModel`.
- Retraining with seed 42 reproduced the identical SHA-256.
- `python -m app.ml.screening.verify` loads the artifact in a fresh process and reports which registry may serve it. Production refuses it with the reasons "model targets a different outcome", "designated for synthetic research only" and "artifact provenance is synthetic".

### 9.5 Inference path (real data)

1. A child plays the visual run; trials are stored and scored server-side.
2. Once the assessment is completed, `extract_profile` derives the features, stored in `session_feature_vectors`.
3. `validate_features` maps them onto `screening-1.0`.
4. `research.py::predict_assessment` checks, in order:
   - the model is loaded and passes `research_eligibility`;
   - the assessment is completed;
   - age is 4–10 when recorded (an unknown age is allowed with a note, because the simulator does not model age);
   - the language is `en`;
   - there are at least 15 scored trials (unscored speech attempts do not count);
   - all four visual-domain accuracies and the required features are present (missing values are never estimated).
5. The model scores the vector. The result is stored once per (assessment, model, version) in `research_predictions`, together with the artifact SHA-256. If the same version later arrives with different bytes, the result is withheld with `model_version_conflict`.
6. The response includes per-feature values, the synthetic training median, an out-of-range flag, and an occlusion effect: the model's own score change when that one value is replaced by the training median.

**API:**
- `GET /api/screening/research/children/{id}` returns the model summary and the child's assessments.
- `POST /api/screening/research/children/{id}/assessments/{aid}/predict` runs the model.

Access requires authentication, research mode enabled (otherwise 404), and the child's owner or a granted educator. Admins and other parents get 404. **UI:** `/research/predictor`, in English and Tamil, linked from the parent dashboard only when research mode is on.

### 9.6 Separation from clinical screening (tested)

- A synthetic model is never eligible for production (designation, card provenance, artifact provenance and target are all checked), even when `SCREENING_MODEL_DIR` points at the research directory.
- A relabelled card is refused by both registries.
- `RESEARCH_DEMO_ENABLED` raises a configuration error in production.
- The parent card (`GET /screening/children/{id}`) never falls back to the research model and never reads `research_predictions`.
- Research results are included in the privacy export and deleted with the child or account.

### 9.7 Limitations

- Every number above reflects the developer-written simulator, not children.
- The simulator's reaction-time and accuracy scales were not calibrated against real children. Real sessions, especially fast automated test clicks, can fall outside the training range; the UI flags this.
- The research model covers only English visual-run assessments. Speech-only runs return `insufficient_observations`.
- Using this model for real decisions would require everything in §5 and §8.5.

### 9.8 Release verification (2026-10-21)

Re-verified on the final tree in a clean, isolated venv (scikit-learn 1.6.1, numpy 2.2.2):
- Artifact SHA-256 matches; it loads in a fresh process (`python -m app.ml.screening.verify`, exit 0); the production registry refuses it.
- The research tests passed on SQLite and PostgreSQL 16.
- The Playwright run scored real game results and rendered the API percentage.
- The production image does not contain the research artifacts, and production refuses `RESEARCH_DEMO_ENABLED`.

The score remains a synthetic-target probability, **not** a real-child dyslexia probability.
