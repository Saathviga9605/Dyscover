# Dyscover Speech ML Pipeline Documentation

This document describes the complete speech recognition fine-tuning and evaluation pipeline implemented in `backend/app/ml/speech/`.

## Overview

The pipeline provides:
1. **Dataset preparation** - Manifest validation, deterministic splitting
2. **Audio preprocessing** - Resampling, normalization, validation
3. **Model management** - Whisper loading via Hugging Face Transformers
4. **Fine-tuning** - Seq2Seq training with Hugging Face Trainer
5. **Evaluation** - WER/CER metrics with proper text normalization
6. **Experiment tracking** - Configuration, registry, reproducibility reports
7. **CLI interface** - All operations via command line
8. **API integration** - Demo endpoints for transcription and comparison

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Speech ML dependencies include:
- `torch>=2.5.1`
- `torchaudio>=2.5.1`
- `transformers>=4.46.3`
- `datasets>=3.2.0`
- `accelerate>=1.3.0`
- `jiwer>=3.0.4`
- `librosa>=0.11.0`
- `soundfile>=0.13.1`

### 2. Prepare Dataset

Create a manifest file (`data/manifest.jsonl`):

```jsonl
{"sample_id": "cv-001", "audio_path": "audio/cv-001.wav", "transcript": "the quick brown fox", "language": "en", "split": "train", "speaker_id": "spk-001", "source_dataset": "common_voice", "license": "CC0", "duration_seconds": 2.3}
{"sample_id": "cv-002", "audio_path": "audio/cv-002.wav", "transcript": "jumps over the lazy dog", "language": "en", "split": "train", "speaker_id": "spk-002", "source_dataset": "common_voice", "license": "CC0", "duration_seconds": 2.1}
```

Supported audio formats: WAV, FLAC, MP3, OGG, M4A

### 3. Validate Manifest

```bash
python -m app.ml.speech.cli validate \
  --manifest data/manifest.jsonl \
  --base-dir data/ \
  --max-duration 30.0 \
  --min-duration 0.5
```

Output: `data/manifest.validation.json` with validation report.

### 4. Create Splits

```bash
python -m app.ml.speech.cli split \
  --manifest data/manifest.jsonl \
  --output-dir data/splits \
  --seed 42 \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --speaker-aware
```

Output:
- `data/splits/manifest_train.jsonl`
- `data/splits/manifest_validation.jsonl`
- `data/splits/manifest_test.jsonl`
- `data/splits/dataset_config.json`

### 5. Fine-Tune Whisper

#### Smoke Test (CPU, fast)

```bash
python -m app.ml.speech.cli train \
  --model openai/whisper-tiny \
  --train-manifest data/splits/manifest_train.jsonl \
  --val-manifest data/splits/manifest_validation.jsonl \
  --test-manifest data/splits/manifest_test.jsonl \
  --output-dir outputs/whisper-smoke \
  --epochs 1 \
  --batch-size 2 \
  --max-steps 10 \
  --fp16 false
```

#### Full Training (GPU recommended)

```bash
python -m app.ml.speech.cli train \
  --model openai/whisper-base \
  --train-manifest data/splits/manifest_train.jsonl \
  --val-manifest data/splits/manifest_validation.jsonl \
  --test-manifest data/splits/manifest_test.jsonl \
  --output-dir outputs/whisper-finetune \
  --epochs 5 \
  --batch-size 8 \
  --lr 1e-5 \
  --warmup 200 \
  --grad-accum 2 \
  --fp16 true \
  --grad-checkpoint
```

### 6. Evaluate Model

```bash
python -m app.ml.speech.cli evaluate \
  --model outputs/whisper-finetune \
  --test-manifest data/splits/manifest_test.jsonl \
  --output-dir outputs/eval \
  --batch-size 8 \
  --num-beams 5
```

### 7. Compare Models

```bash
python -m app.ml.speech.cli compare \
  --pretrained-model openai/whisper-base \
  --finetuned-model outputs/whisper-finetune \
  --test-manifest data/splits/manifest_test.jsonl \
  --output-dir outputs/compare
```

### 8. Run Complete Experiment

```bash
python -m app.ml.speech.cli create-experiment \
  --name my-whisper-exp \
  --model openai/whisper-base \
  --manifest data/manifest.jsonl \
  --language en \
  --output-dir outputs/experiments

python -m app.ml.speech.cli run-experiment \
  --config outputs/experiments/my-whisper-exp-*/experiment_config.json
```

## Detailed Components

### Dataset Manifest Format

Each line is a JSON object with fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| sample_id | string | Yes | Unique identifier |
| audio_path | string | Yes | Relative or absolute path to audio |
| transcript | string | Yes | Reference transcription |
| language | string | Yes | Language code (en, ta, hi, bn, te, mr, gu, kn, ml, pa, or, as) |
| split | string | No | train/validation/test (if pre-split) |
| speaker_id | string | No | Speaker identifier for speaker-aware splitting |
| source_dataset | string | No | Dataset provenance (default: "custom") |
| license | string | No | License info (default: "unknown") |
| duration_seconds | float | No | Audio duration if known |

### Audio Preprocessing

`AudioConfig` parameters:
- `sample_rate`: Target sample rate (default: 16000)
- `max_duration_seconds`: Max allowed duration (default: 30.0)
- `min_duration_seconds`: Min allowed duration (default: 0.5)
- `normalize`: Apply loudness normalization (default: True)
- `target_dbfs`: Target loudness in dBFS (default: -20.0)
- `mono`: Convert to mono (default: True)

Pipeline:
1. Load audio with torchaudio
2. Convert to mono (average channels)
3. Resample to target sample rate
4. Normalize to target dBFS with clipping prevention
5. Return as float32 numpy array for Whisper

### Model Configuration

`WhisperModelConfig`:
- `model_name_or_path`: HF model ID or local path
- `language`: Target language code
- `task`: transcribe or translate
- `device`: auto, cpu, cuda, mps
- `torch_dtype`: float32, float16, bfloat16
- `local_files_only`: Use only local files
- `cache_dir`: Custom cache directory

### Training Configuration

`WhisperFineTuneConfig` key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_model` | openai/whisper-tiny | Pretrained checkpoint |
| `num_train_epochs` | 3 | Training epochs |
| `per_device_train_batch_size` | 4 | Batch size per device |
| `gradient_accumulation_steps` | 2 | Gradient accumulation |
| `learning_rate` | 1e-5 | Learning rate |
| `warmup_steps` | 100 | LR warmup steps |
| `weight_decay` | 0.01 | Weight decay |
| `fp16` | False | Mixed precision FP16 |
| `bf16` | False | Mixed precision BF16 |
| `gradient_checkpointing` | True | Memory optimization |
| `early_stopping_patience` | 3 | Early stopping patience |
| `max_length` | 448 | Max generation length |
| `num_beams` | 5 | Beam search width |

### Evaluation Configuration

`EvaluationConfig`:
- `normalize_text`: Apply text normalization (default: True)
- `remove_punctuation`: Strip punctuation (default: True)
- `lowercase`: Convert to lowercase (default: True)
- `strip_whitespace`: Normalize whitespace (default: True)

WER/CER computed using `jiwer` library on normalized text.

### Experiment Tracking

Each experiment records:
- Experiment ID and name
- Base model and revision
- Dataset name, version, manifest hash
- Split seed and strategy
- Full training and evaluation configs
- Environment: Python, PyTorch, Transformers versions, CUDA
- Timestamps: created, started, completed
- Status: created/training/evaluating/completed/failed
- Artifact paths: checkpoints, evaluation results
- Training metrics and evaluation metrics

Reports generated as Markdown (`experiment_report.md`) and JSON (`experiment_metadata.json`).

## API Integration

### Hugging Face Whisper Provider

Enable in backend:
```bash
DYSCOVER_ASR_PROVIDER=huggingface-whisper
DYSCOVER_HF_WHISPER_MODEL=openai/whisper-tiny
DYSCOVER_HF_WHISPER_LANGUAGE=en
DYSCOVER_HF_WHISPER_DEVICE=auto
DYSCOVER_HF_WHISPER_DTYPE=float32
```

### Demo Endpoints

```
GET  /api/speech/demo/providers     # List available providers
POST /api/speech/demo/transcribe    # Transcribe audio (multipart/form-data)
POST /api/speech/demo/compare       # Compare providers on same audio
GET  /api/speech/demo/models        # Show model configurations
```

Transcribe request:
- `file`: Audio file (multipart)
- `language`: Language code (default: en)
- `provider`: Override provider (optional)
- `consent`: Must be "true" (required)

### Frontend Demo

```tsx
import { SpeechDemo } from '@/speech';

function MyPage() {
  return <SpeechDemo />;
}
```

## Reproducibility

All pipeline operations are deterministic given:
- Fixed random seed (default: 42)
- Fixed dataset manifest and splits
- Fixed training configuration
- Recorded environment versions

Experiment reports include:
- Dataset manifest SHA256
- Split configuration
- Complete training config
- Environment snapshot
- Model checkpoint SHA256

## Troubleshooting

### Out of Memory
- Reduce `per_device_train_batch_size`
- Increase `gradient_accumulation_steps`
- Enable `gradient_checkpointing`
- Use `fp16` or `bf16`
- Use smaller model (whisper-tiny)

### Slow Training
- Use GPU (`device=cuda`)
- Increase batch size if memory allows
- Disable gradient checkpointing if memory allows
- Use `max_steps` for quick iteration

### Validation Errors
- Check audio files exist at paths in manifest
- Verify transcripts are non-empty
- Ensure language codes are supported
- Check audio duration within limits

### Model Loading Fails
- Verify HF model ID is correct
- Check internet access for HF Hub
- For local paths, ensure path exists
- Check transformers version compatibility

## License and Attribution

- Whisper model: OpenAI (MIT license)
- Transformers: Hugging Face (Apache 2.0)
- jiwer: Apache 2.0
- torchaudio: BSD-3-Clause

Dataset licenses must be respected. Common Voice is CC0. LibriSpeech is public domain.

## Future Work

See [Edge Deployment](docs/speech-architecture.md#edge-deployment-future-work) section for deployment roadmap.