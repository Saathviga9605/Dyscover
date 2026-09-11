# Stage 3.5 hardening status

## Implemented now

- Explicit ML states: `DEMO`, `OBSERVATION_ONLY`, `RESEARCH`, `MODEL_INFERENCE`, and `UNAVAILABLE`.
- Canonical feature metadata registry with modality, unit, range, aggregation, and version fields.
- Feature status distinguishes available, missing, invalid, and not applicable values.
- Data-quality reports classify `ok`, `warning`, and `invalid` sessions and report zero-trial sessions, incomplete trials, missingness, and modality availability.
- Dataset rows support immutable JSON/CSV artifacts with manifests, versions, timestamps, modalities, labels, split strategy, and artifact hashes.
- Subject-level random splitting and grouped cross-validation folds prevent subject leakage.
- Training is explicit and rejects missing IDs, missing labels, single-class targets, and unsupported algorithms.
- Baseline model pipelines keep imputation/scaling inside the model pipeline.
- Model registry entries include algorithm and hyperparameter provenance and remain unavailable until governed training occurs.
- Observation profiles and parent UI clearly separate measured observations from unavailable model inference.
- Legacy score-to-dyslexia-probability UI has been removed from active and preserved legacy execution.

## Not available yet

There is no validated labeled dataset, trained model artifact, clinical validation, authentication/authorization layer, connected WebGazer provider, speech/NLP provider, or real multimodal inference. These are deliberate research prerequisites, not hidden fallbacks.

## Governance rules

Demo data must never enter training. Subject IDs remain grouping identifiers, not features. Missing modalities are not replaced with meaningful zeros. A missing model returns structured `UNAVAILABLE` state. Dyscover does not diagnose dyslexia or convert activity scores into clinical probabilities.