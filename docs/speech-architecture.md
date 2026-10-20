# Stage 4 speech and reading infrastructure

Stage 4 adds an optional `backend/app/speech` subsystem. Its provider boundary is `SpeechProvider`; the default provider is explicitly `NOT_CONFIGURED` and never pretends to transcribe audio.

The deterministic pipeline is:

`ReadingTask -> Transcript -> expected-text alignment -> reading features + text features -> existing ML feature registry`.

Alignment reports matched words, substitutions, omissions, insertions, repetitions, and order differences. Fluency features require real duration or word timestamps. Missing audio, transcript, timestamps, or expected text remain unavailable rather than becoming zero.

Speech features are observable research/educational features. They are not diagnostic biomarkers. Raw audio is not accepted by the Stage 4 API and is not stored in feature vectors. Future providers may reference controlled audio storage without changing the transcript/alignment contract.

## Current APIs

- `GET /api/speech/status`
- `POST /api/speech/analyze`
- `POST /api/speech/sessions`
- `GET /api/speech/sessions/{speech_session_id}`

No provider, cloud API key, speech model, pronunciation model, or clinical speech classifier is configured by default.

Speech sessions store only assessment/trial references, task metadata, language, provider metadata, duration, and an `audio_available` flag. They do not accept raw audio blobs.

## Hugging Face Whisper Provider (Stage 4+)

An optional local ASR provider using Hugging Face Transformers' Whisper implementation is available.

### Configuration

Enable via environment variables:

```bash
# Enable Hugging Face Whisper provider
DYSCOVER_ASR_PROVIDER=huggingface-whisper

# Model selection (any HF Whisper checkpoint or local path)
DYSCOVER_HF_WHISPER_MODEL=openai/whisper-tiny

# Language for transcription
DYSCOVER_HF_WHISPER_LANGUAGE=en

# Device: auto, cpu, cuda, mps
DYSCOVER_HF_WHISPER_DEVICE=auto

# Torch dtype: float32, float16, bfloat16
DYSCOVER_HF_WHISPER_DTYPE=float32

# Optional local cache directory
DYSCOVER_HF_WHISPER_CACHE=/path/to/cache
```

### Provider Features

- Loads Whisper models from Hugging Face Hub or local path
- Supports all Whisper checkpoints (tiny, base, small, medium, large, large-v2, large-v3)
- CPU and GPU inference with automatic device detection
- Configurable torch dtype for memory/performance trade-off
- Word-level timestamps when available
- Integrates with existing `SpeechProvider` interface

### Health Check

The provider reports `AVAILABLE` when a model name or path is configured, `NOT_CONFIGURED` otherwise.

## Faster-Whisper Provider (Existing)

The existing `faster-whisper` provider remains available:

```bash
DYSCOVER_ASR_PROVIDER=faster-whisper
DYSCOVER_ASR_MODEL=small
DYSCOVER_ASR_MODEL_PATH=/path/to/local/model
DYSCOVER_ASR_DEVICE=cpu
DYSCOVER_ASR_COMPUTE_TYPE=int8
DYSCOVER_ASR_ALLOW_MODEL_LOAD=true
```

## Speech ML Pipeline (Research)

A complete fine-tuning and evaluation pipeline is available under `backend/app/ml/speech/`.

### Components

- **Dataset**: Manifest format (JSONL/CSV), validation, deterministic splits
- **Audio**: Preprocessing (resample to 16kHz, mono, normalize)
- **Model**: WhisperModelManager, HuggingFaceWhisperProvider
- **Training**: WhisperFineTuner using Hugging Face Trainer
- **Evaluation**: WER/CER metrics with text normalization
- **Experiment**: Configuration, registry, reproducibility reports

### CLI Commands

```bash
# Validate dataset manifest
python -m app.ml.speech.cli validate --manifest data/manifest.jsonl --base-dir data/

# Create train/val/test splits
python -m app.ml.speech.cli split --manifest data/manifest.jsonl --output-dir data/splits --seed 42

# Fine-tune Whisper (smoke test)
python -m app.ml.speech.cli train --config configs/speech/whisper-smoke-test.yaml

# Fine-tune Whisper (full)
python -m app.ml.speech.cli train --config configs/speech/whisper-finetune.yaml

# Evaluate model
python -m app.ml.speech.cli evaluate --model openai/whisper-tiny --test-manifest data/splits/manifest_test.jsonl

# Compare pretrained vs fine-tuned
python -m app.ml.speech.cli compare --pretrained-model openai/whisper-tiny --finetuned-model outputs/model --test-manifest data/splits/manifest_test.jsonl

# Create experiment config
python -m app.ml.speech.cli create-experiment --name my-experiment --model openai/whisper-tiny --manifest data/manifest.jsonl

# Run full experiment
python -m app.ml.speech.cli run-experiment --config outputs/experiment_config.json
```

### Manifest Format (JSONL)

```jsonl
{"sample_id": "sample-001", "audio_path": "audio/sample-001.wav", "transcript": "the cat sat on the mat", "language": "en", "split": "train", "speaker_id": "spk-001", "source_dataset": "common_voice", "license": "CC0", "duration_seconds": 2.5}
```

### Dataset Preparation

1. Collect audio files and transcripts
2. Create manifest with metadata
3. Validate: `python -m app.ml.speech.cli validate --manifest manifest.jsonl`
4. Split: `python -m app.ml.speech.cli split --manifest manifest.jsonl --output-dir splits/`
5. Review split statistics

### Fine-Tuning

1. Configure training in YAML or via CLI
2. Run training: `python -m app.ml.speech.cli train --config config.yaml`
3. Checkpoints saved to `output_dir/`
4. Best model selected by validation WER

### Evaluation

- Computes Word Error Rate (WER) and Character Error Rate (CER)
- Text normalization: lowercase, punctuation removal, whitespace stripping
- Per-sample and aggregate metrics
- Comparison between baseline and fine-tuned models

## Demo API Endpoints

New endpoints for demonstration and testing:

- `GET /api/speech/demo/providers` - List available providers and status
- `POST /api/speech/demo/transcribe` - Transcribe uploaded audio (requires consent)
- `POST /api/speech/demo/compare` - Compare multiple providers on same audio
- `GET /api/speech/demo/models` - Show configured model parameters

### Frontend Demo

A `SpeechDemo` React component is available at `frontend/src/speech/SpeechDemo.tsx` for interactive testing.

## Edge Deployment (Future Work)

The following steps are needed for deploying trained models on edge devices:

1. **Model Export**: Convert fine-tuned Whisper to ONNX/TFLite/CoreML
2. **Quantization**: INT8/INT4 quantization for reduced size and faster inference
3. **Runtime Selection**: ONNX Runtime, TensorRT, TFLite, CoreML, or whisper.cpp
4. **Hardware Testing**: Benchmark on Raspberry Pi, Jetson, mobile devices
5. **Streaming Inference**: Chunked processing for real-time applications
6. **Accuracy Validation**: Compare quantized model WER/CER against full precision
7. **Privacy Review**: Ensure on-device processing meets privacy requirements

No edge deployment has been performed; this section documents required future work only.

## Research Limitations

- **No Clinical Validation**: Speech features are observational, not diagnostic
- **Synthetic Data Separation**: Dyscover's synthetic data is never mixed with real speech training data
- **Reproducibility**: All experiments record config, seed, environment, and dataset hashes
- **Resource Requirements**: Fine-tuning requires GPU; inference works on CPU
- **Language Support**: Primarily tested on English; multilingual support depends on Whisper checkpoint