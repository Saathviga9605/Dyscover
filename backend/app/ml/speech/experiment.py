"""Experiment configuration and model registry for speech research."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

from .training import WhisperFineTuneConfig
from .evaluation import EvaluationConfig, EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class SpeechExperimentConfig:
    """Complete experiment configuration for speech research."""

    experiment_id: str
    experiment_name: str
    description: str = ""

    # Base model
    base_model: str = "openai/whisper-tiny"
    base_model_revision: str = "main"

    # Dataset
    dataset_name: str = "custom"
    dataset_version: str = "1.0"
    dataset_manifest: str = ""
    dataset_manifest_hash: str = ""
    dataset_split_seed: int = 42
    language: str = "en"

    # Training config
    training_config: WhisperFineTuneConfig | None = None

    # Evaluation config
    evaluation_config: EvaluationConfig | None = None

    # Audio preprocessing
    audio_config: dict[str, Any] = field(default_factory=dict)

    # Environment (auto-filled)
    python_version: str = field(default_factory=lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    torch_version: str = field(default_factory=lambda: torch.__version__)
    transformers_version: str = ""
    platform: str = field(default_factory=lambda: platform.platform())
    cuda_available: bool = field(default_factory=lambda: torch.cuda.is_available())
    cuda_version: str = ""
    device: str = "auto"

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None

    # Status
    status: str = "created"  # created, training, evaluating, completed, failed
    training_status: str = "pending"
    evaluation_status: str = "pending"

    # Artifacts
    output_dir: str = ""
    model_checkpoint_path: str = ""
    evaluation_result_path: str = ""

    def __post_init__(self):
        if self.transformers_version == "":
            try:
                import transformers
                self.transformers_version = transformers.__version__
            except ImportError:
                self.transformers_version = "unknown"
        if self.cuda_available and self.cuda_version == "":
            self.cuda_version = torch.version.cuda or "unknown"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert nested configs to dicts
        if self.training_config:
            d["training_config"] = asdict(self.training_config)
        if self.evaluation_config:
            d["evaluation_config"] = asdict(self.evaluation_config)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpeechExperimentConfig:
        training_config = data.pop("training_config", None)
        evaluation_config = data.pop("evaluation_config", None)
        config = cls(**data)
        if training_config:
            config.training_config = WhisperFineTuneConfig(**training_config)
        if evaluation_config:
            config.evaluation_config = EvaluationConfig(**evaluation_config)
        return config

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SpeechExperimentConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


@dataclass
class SpeechModelInfo:
    """Metadata for a trained speech model."""

    model_id: str
    experiment_id: str
    base_model: str
    base_model_revision: str
    language: str
    dataset_name: str
    dataset_version: str
    dataset_manifest_hash: str
    training_config: dict[str, Any]
    training_metrics: dict[str, Any] = field(default_factory=dict)
    evaluation_metrics: dict[str, Any] = field(default_factory=dict)
    checkpoint_path: str = ""
    checkpoint_sha256: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "trained"  # trained, validated, deprecated, failed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpeechModelInfo:
        return cls(**data)


class SpeechModelRegistry:
    """Registry for managing speech model checkpoints and metadata."""

    def __init__(self, registry_dir: Path):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.registry_dir / "registry_index.json"
        self._index: dict[str, SpeechModelInfo] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                self._index = {k: SpeechModelInfo.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load registry index: {e}")
                self._index = {}

    def _save_index(self) -> None:
        data = {k: v.to_dict() for k, v in self._index.items()}
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register(self, model_info: SpeechModelInfo) -> SpeechModelInfo:
        """Register a trained model."""
        if model_info.model_id in self._index:
            logger.warning(f"Model {model_info.model_id} already registered, updating")

        # Verify checkpoint
        if model_info.checkpoint_path:
            cp = Path(model_info.checkpoint_path)
            if cp.exists():
                if cp.is_dir():
                    # Hash the model.safetensors or pytorch_model.bin
                    model_files = list(cp.glob("*.safetensors")) + list(cp.glob("*.bin"))
                    if model_files:
                        model_info.checkpoint_sha256 = hashlib.sha256(model_files[0].read_bytes()).hexdigest()
                else:
                    model_info.checkpoint_sha256 = hashlib.sha256(cp.read_bytes()).hexdigest()

        self._index[model_info.model_id] = model_info
        self._save_index()
        logger.info(f"Registered model: {model_info.model_id}")
        return model_info

    def get(self, model_id: str) -> SpeechModelInfo | None:
        return self._index.get(model_id)

    def list_models(self, status: str | None = None) -> list[SpeechModelInfo]:
        models = list(self._index.values())
        if status:
            models = [m for m in models if m.status == status]
        return sorted(models, key=lambda m: m.created_at, reverse=True)

    def unregister(self, model_id: str) -> bool:
        if model_id in self._index:
            del self._index[model_id]
            self._save_index()
            return True
        return False


def create_experiment_config(
    experiment_name: str,
    base_model: str = "openai/whisper-tiny",
    dataset_manifest: str = "",
    language: str = "en",
    output_dir: str = "outputs/speech_experiments",
    training_overrides: dict[str, Any] | None = None,
    evaluation_overrides: dict[str, Any] | None = None,
) -> SpeechExperimentConfig:
    """Create a complete experiment configuration with defaults."""
    import uuid

    experiment_id = f"{experiment_name}-{uuid.uuid4().hex[:8]}"
    out_dir = Path(output_dir) / experiment_id

    # Training config
    train_config = WhisperFineTuneConfig(
        base_model=base_model,
        language=language,
        train_manifest=dataset_manifest.replace(".jsonl", "_train.jsonl") if dataset_manifest else "",
        validation_manifest=dataset_manifest.replace(".jsonl", "_validation.jsonl") if dataset_manifest else "",
        test_manifest=dataset_manifest.replace(".jsonl", "_test.jsonl") if dataset_manifest else "",
        output_dir=str(out_dir / "model"),
    )
    if training_overrides:
        for k, v in training_overrides.items():
            if hasattr(train_config, k):
                setattr(train_config, k, v)

    # Evaluation config
    eval_config = EvaluationConfig(
        model_name_or_path=base_model,
        language=language,
        test_manifest=dataset_manifest.replace(".jsonl", "_test.jsonl") if dataset_manifest else "",
        output_dir=str(out_dir / "evaluation"),
    )
    if evaluation_overrides:
        for k, v in evaluation_overrides.items():
            if hasattr(eval_config, k):
                setattr(eval_config, k, v)

    # Dataset hash
    dataset_hash = ""
    if dataset_manifest and Path(dataset_manifest).exists():
        dataset_hash = hashlib.sha256(Path(dataset_manifest).read_bytes()).hexdigest()

    return SpeechExperimentConfig(
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        base_model=base_model,
        dataset_manifest=dataset_manifest,
        dataset_manifest_hash=dataset_hash,
        language=language,
        training_config=train_config,
        evaluation_config=eval_config,
        output_dir=str(out_dir),
    )


def generate_experiment_report(
    experiment: SpeechExperimentConfig,
    evaluation_result: EvaluationResult | None = None,
) -> str:
    """Generate a Markdown experiment report."""
    lines = [
        f"# Experiment Report: {experiment.experiment_name}",
        f"**Experiment ID:** {experiment.experiment_id}",
        f"**Status:** {experiment.status}",
        f"**Created:** {experiment.created_at}",
        f"**Completed:** {experiment.completed_at or 'N/A'}",
        "",
        "## Configuration",
        f"- **Base Model:** {experiment.base_model} ({experiment.base_model_revision})",
        f"- **Dataset:** {experiment.dataset_name} v{experiment.dataset_version}",
        f"- **Dataset Manifest:** {experiment.dataset_manifest}",
        f"- **Dataset Hash:** {experiment.dataset_manifest_hash}",
        f"- **Split Seed:** {experiment.dataset_split_seed}",
        f"- **Language:** {experiment.language}",
        f"- **Output Directory:** {experiment.output_dir}",
        "",
        "### Training Configuration",
    ]

    if experiment.training_config:
        tc = experiment.training_config
        lines.extend([
            f"- **Epochs:** {tc.num_train_epochs}",
            f"- **Batch Size:** {tc.per_device_train_batch_size}",
            f"- **Learning Rate:** {tc.learning_rate}",
            f"- **Warmup Steps:** {tc.warmup_steps}",
            f"- **Weight Decay:** {tc.weight_decay}",
            f"- **Gradient Accumulation:** {tc.gradient_accumulation_steps}",
            f"- **FP16/BF16:** {tc.fp16}/{tc.bf16}",
            f"- **Gradient Checkpointing:** {tc.gradient_checkpointing}",
            f"- **Early Stopping Patience:** {tc.early_stopping_patience}",
        ])
    else:
        lines.append("- *No training configuration*")

    lines.extend([
        "",
        "### Evaluation Configuration",
    ])

    if experiment.evaluation_config:
        ec = experiment.evaluation_config
        lines.extend([
            f"- **Test Manifest:** {ec.test_manifest}",
            f"- **Batch Size:** {ec.batch_size}",
            f"- **Max Length:** {ec.max_length}",
            f"- **Num Beams:** {ec.num_beams}",
            f"- **Text Normalization:** {ec.normalize_text}",
            f"- **Remove Punctuation:** {ec.remove_punctuation}",
            f"- **Lowercase:** {ec.lowercase}",
        ])
    else:
        lines.append("- *No evaluation configuration*")

    lines.extend([
        "",
        "## Environment",
        f"- **Python:** {experiment.python_version}",
        f"- **PyTorch:** {experiment.torch_version}",
        f"- **Transformers:** {experiment.transformers_version}",
        f"- **Platform:** {experiment.platform}",
        f"- **CUDA Available:** {experiment.cuda_available}",
        f"- **CUDA Version:** {experiment.cuda_version}",
        f"- **Device:** {experiment.device}",
        "",
    ])

    if evaluation_result:
        lines.extend([
            "## Evaluation Results",
            f"- **Model:** {evaluation_result.model_name}",
            f"- **Test Samples:** {evaluation_result.num_samples}",
            f"- **WER:** {evaluation_result.wer:.4f} ({evaluation_result.wer:.2%})",
            f"- **CER:** {evaluation_result.cer:.4f} ({evaluation_result.cer:.2%})",
            f"- **WER Median:** {evaluation_result.wer_median:.4f}",
            f"- **CER Median:** {evaluation_result.cer_median:.4f}",
            f"- **Dataset Hash:** {evaluation_result.dataset_hash}",
            "",
        ])

    if experiment.training_status != "pending" and experiment.training_config:
        lines.extend([
            "## Training Results",
            f"- **Status:** {experiment.training_status}",
            f"- **Model Checkpoint:** {experiment.model_checkpoint_path}",
        ])
        if experiment.training_config:
            tc = experiment.training_config
            # These would be filled after training
            lines.append("")

    lines.extend([
        "## Reproducibility",
        f"To reproduce this experiment, run:",
        f"```bash",
        f"python -m app.ml.speech.cli train --config {experiment.output_dir}/experiment_config.json",
        f"```",
        "",
        "## Notes",
        "- All metrics computed on held-out test set",
        "- Text normalization applied for WER/CER (lowercase, punctuation removal, whitespace stripping)",
        "- Speaker-aware splitting used when speaker_id available in manifest",
    ])

    return "\n".join(lines)