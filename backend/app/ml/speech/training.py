"""Whisper fine-tuning pipeline using Hugging Face Trainer."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset, DatasetDict
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)
from transformers.trainer_callback import EarlyStoppingCallback

from .audio import AudioPreprocessor, AudioConfig
from .dataset import SpeechManifestEntry, load_manifest
from .model import WhisperModelConfig, WhisperModelManager

logger = logging.getLogger(__name__)


@dataclass
class WhisperFineTuneConfig:
    """Configuration for Whisper fine-tuning."""

    # Model
    base_model: str = "openai/whisper-tiny"
    language: str = "en"
    task: str = "transcribe"

    # Data
    train_manifest: str = ""
    validation_manifest: str = ""
    test_manifest: str = ""
    data_base_dir: str = ""
    audio_config: dict[str, Any] = field(default_factory=dict)

    # Training
    output_dir: str = "outputs/whisper-finetune"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 2
    learning_rate: float = 1e-5
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_steps: int = -1
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 50
    eval_strategy: str = "steps"
    save_strategy: str = "steps"
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "wer"
    greater_is_better: bool = False

    # Optimization
    fp16: bool = False
    bf16: bool = False
    gradient_checkpointing: bool = True
    dataloader_num_workers: int = 0
    remove_unused_columns: bool = False

    # Early stopping
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.001

    # Generation
    max_length: int = 448
    num_beams: int = 5

    # Reproducibility
    seed: int = 42

    # Resume
    resume_from_checkpoint: str | None = None

    def to_training_args(self) -> Seq2SeqTrainingArguments:
        """Convert to Seq2SeqTrainingArguments."""
        return Seq2SeqTrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=self.num_train_epochs,
            per_device_train_batch_size=self.per_device_train_batch_size,
            per_device_eval_batch_size=self.per_device_eval_batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            learning_rate=self.learning_rate,
            warmup_steps=self.warmup_steps,
            weight_decay=self.weight_decay,
            max_steps=self.max_steps if self.max_steps > 0 else None,
            save_steps=self.save_steps,
            eval_steps=self.eval_steps,
            logging_steps=self.logging_steps,
            eval_strategy=self.eval_strategy,
            save_strategy=self.save_strategy,
            load_best_model_at_end=self.load_best_model_at_end,
            metric_for_best_model=self.metric_for_best_model,
            greater_is_better=self.greater_is_better,
            fp16=self.fp16,
            bf16=self.bf16,
            gradient_checkpointing=self.gradient_checkpointing,
            dataloader_num_workers=self.dataloader_num_workers,
            remove_unused_columns=self.remove_unused_columns,
            predict_with_generate=True,
            generation_max_length=self.max_length,
            generation_num_beams=self.num_beams,
            seed=self.seed,
            report_to="none",
            resume_from_checkpoint=self.resume_from_checkpoint,
        )


class WhisperDataCollator:
    """Data collator for Whisper sequence-to-sequence training."""

    def __init__(self, processor: WhisperProcessor, audio_preprocessor: AudioPreprocessor):
        self.processor = processor
        self.audio_preprocessor = audio_preprocessor

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        # Process audio
        audio_arrays = [f["audio_array"] for f in features]
        input_features = self.processor.feature_extractor(
            audio_arrays, sampling_rate=16000, return_tensors="pt"
        ).input_features

        # Process labels
        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        # Replace padding with -100 for loss
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )

        # Remove BOS token if present
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        return {
            "input_features": input_features,
            "labels": labels,
        }


def prepare_dataset_entry(
    entry: SpeechManifestEntry,
    audio_preprocessor: AudioPreprocessor,
    processor: WhisperProcessor,
    base_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Prepare a single dataset entry for training."""
    try:
        audio_path = Path(entry.audio_path)
        if base_dir and not audio_path.is_absolute():
            audio_path = base_dir / audio_path

        audio_array = audio_preprocessor.preprocess_for_whisper(audio_path)

        # Tokenize transcript
        labels = processor.tokenizer(
            entry.transcript,
            max_length=448,
            truncation=True,
        ).input_ids

        return {
            "audio_array": audio_array,
            "labels": labels,
            "sample_id": entry.sample_id,
            "language": entry.language,
        }
    except Exception as e:
        logger.warning(f"Failed to prepare entry {entry.sample_id}: {e}")
        return None


def build_hf_dataset(
    entries: list[SpeechManifestEntry],
    audio_preprocessor: AudioPreprocessor,
    processor: WhisperProcessor,
    base_dir: Path | None = None,
) -> Dataset:
    """Build Hugging Face Dataset from manifest entries."""
    prepared = []
    for entry in entries:
        result = prepare_dataset_entry(entry, audio_preprocessor, processor, base_dir)
        if result:
            prepared.append(result)

    if not prepared:
        raise ValueError("No valid entries in dataset")

    return Dataset.from_list(prepared)


def build_dataset_dict(
    train_entries: list[SpeechManifestEntry],
    val_entries: list[SpeechManifestEntry],
    test_entries: list[SpeechManifestEntry],
    audio_preprocessor: AudioPreprocessor,
    processor: WhisperProcessor,
    base_dir: Path | None = None,
) -> DatasetDict:
    """Build DatasetDict with train/validation/test splits."""
    return DatasetDict({
        "train": build_hf_dataset(train_entries, audio_preprocessor, processor, base_dir),
        "validation": build_hf_dataset(val_entries, audio_preprocessor, processor, base_dir),
        "test": build_hf_dataset(test_entries, audio_preprocessor, processor, base_dir),
    })


class WhisperFineTuner:
    """Orchestrates Whisper fine-tuning with Hugging Face Trainer."""

    def __init__(self, config: WhisperFineTuneConfig):
        self.config = config
        self.trainer: Seq2SeqTrainer | None = None
        self.processor: WhisperProcessor | None = None
        self.model: WhisperForConditionalGeneration | None = None

    def setup(self) -> None:
        """Initialize model, processor, and data."""
        logger.info("Setting up Whisper fine-tuning...")

        # Load processor and model
        self.processor = WhisperProcessor.from_pretrained(
            self.config.base_model,
            language=self.config.language,
            task=self.config.task,
        )

        model_manager = WhisperModelManager(WhisperModelConfig(
            model_name_or_path=self.config.base_model,
            language=self.config.language,
            task=self.config.task,
        ))
        self.model = model_manager._model or model_manager.load()[0]

        # Set generation config
        self.model.generation_config.language = self.config.language
        self.model.generation_config.task = self.config.task
        self.model.generation_config.forced_decoder_ids = None

    def prepare_data(self) -> DatasetDict:
        """Load and prepare datasets from manifests."""
        base_dir = Path(self.config.data_base_dir) if self.config.data_base_dir else None
        audio_config = AudioConfig(**self.config.audio_config)
        audio_preprocessor = AudioPreprocessor(audio_config)

        train_entries = load_manifest(Path(self.config.train_manifest))
        val_entries = load_manifest(Path(self.config.validation_manifest))
        test_entries = load_manifest(Path(self.config.test_manifest))

        logger.info(f"Loaded {len(train_entries)} train, {len(val_entries)} val, {len(test_entries)} test entries")

        return build_dataset_dict(
            train_entries, val_entries, test_entries,
            audio_preprocessor, self.processor, base_dir
        )

    def train(self) -> dict[str, Any]:
        """Run fine-tuning and return results."""
        if self.model is None or self.processor is None:
            self.setup()

        dataset = self.prepare_data()

        # Create data collator
        audio_preprocessor = AudioPreprocessor(AudioConfig(**self.config.audio_config))
        data_collator = WhisperDataCollator(self.processor, audio_preprocessor)

        # Training arguments
        training_args = self.config.to_training_args()

        # Callbacks
        callbacks = [EarlyStoppingCallback(
            early_stopping_patience=self.config.early_stopping_patience,
            early_stopping_threshold=self.config.early_stopping_threshold,
        )]

        # Trainer
        self.trainer = Seq2SeqTrainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["validation"],
            data_collator=data_collator,
            tokenizer=self.processor.feature_extractor,
            callbacks=callbacks,
        )

        # Train
        logger.info("Starting training...")
        train_result = self.trainer.train(resume_from_checkpoint=self.config.resume_from_checkpoint)

        # Save final model
        self.trainer.save_model()
        self.processor.save_pretrained(self.config.output_dir)

        # Save training config and metadata
        self._save_experiment_metadata(train_result)

        return {
            "train_metrics": train_result.metrics,
            "model_path": self.config.output_dir,
        }

    def evaluate(self, split: str = "test") -> dict[str, Any]:
        """Evaluate on specified split."""
        if self.trainer is None:
            raise RuntimeError("Trainer not initialized. Call train() or setup() first.")

        # We need to re-prepare test data with the current processor
        dataset = self.prepare_data()
        test_dataset = dataset[split]

        # Re-create trainer with test dataset
        audio_preprocessor = AudioPreprocessor(AudioConfig(**self.config.audio_config))
        data_collator = WhisperDataCollator(self.processor, audio_preprocessor)

        eval_trainer = Seq2SeqTrainer(
            model=self.model,
            args=self.config.to_training_args(),
            eval_dataset=test_dataset,
            data_collator=data_collator,
            tokenizer=self.processor.feature_extractor,
        )

        eval_results = eval_trainer.evaluate()
        return eval_results

    def _save_experiment_metadata(self, train_result: Any) -> None:
        """Save experiment configuration and results."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "experiment_type": "whisper_finetune",
            "base_model": self.config.base_model,
            "language": self.config.language,
            "task": self.config.task,
            "config": asdict(self.config),
            "train_metrics": train_result.metrics,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            },
        }

        # Add dataset info
        for split_name, manifest_path in [
            ("train", self.config.train_manifest),
            ("validation", self.config.validation_manifest),
            ("test", self.config.test_manifest),
        ]:
            if manifest_path:
                manifest_file = Path(manifest_path)
                if manifest_file.exists():
                    metadata[f"{split_name}_manifest_hash"] = hashlib.sha256(
                        manifest_file.read_bytes()
                    ).hexdigest()

        metadata_path = output_dir / "experiment_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        logger.info(f"Experiment metadata saved to {metadata_path}")


def run_finetune(config: WhisperFineTuneConfig) -> dict[str, Any]:
    """Convenience function to run fine-tuning end-to-end."""
    finetuner = WhisperFineTuner(config)
    finetuner.setup()
    result = finetuner.train()
    return result