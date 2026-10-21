# AI/ML Validation Report

Updated 2026-10-21. Evidence file: `docs/readiness/evidence/synthetic-multiseed.json` (produced by `python -m app.ml.synthetic.experiment --seeds 1 2 3 4 5 --subjects 60`).

**Bottom line:** Dyscover has no model validated on real children's data. All trained models are research artifacts fitted to **synthetic, simulator-defined** interaction profiles. Predictive inference in the product is disabled (`POST /api/ml/predict/session/{id}` always returns `status: unavailable`), and the production model registry refuses models flagged `synthetic`. Nothing in this report is evidence of dyslexia detection accuracy.

## 1. What runs in the product today

| Capability | Status | Evidence |
|---|---|---|
| Per-session feature extraction from persisted trials/events/gaze/speech (40 registered features, schema 1.0) | Implemented and tested | `app/ml/features.py`, `tests/test_api.py::test_end_to_end_telemetry_reaches_feature_extraction` |
| Missing modalities | Reported as `value: null, available: false` — never zero | `features.py` `_append_gaze_features/_append_speech_features`; modality summary returns `null` coverage when nothing was recorded |
| Descriptive "screening profile" (observations, data quality, limitations) | Implemented; descriptive only | `app/ml/profile.py` |
| Predictive classification | **Deliberately unavailable** | `app/ml/routes.py::predict` |
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
