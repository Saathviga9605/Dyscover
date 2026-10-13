# Model training

Three scikit-learn baselines are available as offline interfaces: logistic regression, random forest, and gradient boosting. They use imputation where feature values are unavailable; training rejects single-class labels. No model is trained or registered in this repository because no validated labeled dataset is present.

Training must record feature schema, dataset version, model version, seed, parameters, and evaluation configuration before a model can move from unavailable to research status.

The executable research lifecycle is in `backend/app/ml/training.py`. It trains only on
explicitly supplied labels, keeps subjects separated, writes a hashed pickle artifact and
metadata sidecar, and validates the feature schema and artifact hash before inference.
Artifacts created by tests are not added to the application registry.

## Optional local speech recognition

Browser speech recognition remains the default client-side path. A backend provider can be
enabled only when explicitly configured with:

```text
DYSCOVER_ASR_PROVIDER=faster-whisper
DYSCOVER_ASR_MODEL=small
DYSCOVER_ASR_ALLOW_MODEL_LOAD=true
```

`faster-whisper` is an optional dependency and model files are not downloaded by the
application. A local model path can be supplied with `DYSCOVER_ASR_MODEL_PATH`, along with
`DYSCOVER_ASR_DEVICE` and `DYSCOVER_ASR_COMPUTE_TYPE`. The adapter accepts English (`en`)
and Tamil (`ta`) only, requires explicit audio consent, processes a local audio reference,
and does not persist audio or transcripts. If the dependency or model is unavailable, the
provider reports an unavailable state and the browser path remains unaffected.
