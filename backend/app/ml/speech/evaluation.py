"""WER/CER evaluation service for speech recognition models."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jiwer
import numpy as np
import torch
from transformers import WhisperProcessor

from .audio import AudioPreprocessor, AudioConfig
from .dataset import SpeechManifestEntry, load_manifest
from .model import WhisperModelManager, WhisperModelConfig, HuggingFaceWhisperProvider

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """Configuration for model evaluation."""

    # Model
    model_name_or_path: str = "openai/whisper-tiny"
    language: str = "en"
    task: str = "transcribe"
    device: str = "auto"
    torch_dtype: str = "float32"

    # Data
    test_manifest: str = ""
    data_base_dir: str = ""
    audio_config: dict[str, Any] = field(default_factory=dict)

    # Evaluation
    batch_size: int = 8
    max_length: int = 448
    num_beams: int = 5

    # Output
    output_dir: str = "outputs/whisper-eval"
    save_predictions: bool = True

    # Text normalization
    normalize_text: bool = True
    remove_punctuation: bool = True
    lowercase: bool = True
    strip_whitespace: bool = True


@dataclass
class SamplePrediction:
    sample_id: str
    reference: str
    hypothesis: str
    wer: float
    cer: float
    language: str
    duration_seconds: float | None = None


@dataclass
class EvaluationResult:
    model_name: str
    model_path: str
    dataset_manifest: str
    dataset_hash: str
    num_samples: int
    wer: float
    cer: float
    wer_median: float
    cer_median: float
    samples: list[SamplePrediction]
    evaluation_config: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "dataset_manifest": self.dataset_manifest,
            "dataset_hash": self.dataset_hash,
            "num_samples": self.num_samples,
            "wer": self.wer,
            "cer": self.cer,
            "wer_median": self.wer_median,
            "cer_median": self.cer_median,
            "samples": [asdict(s) for s in self.samples],
            "evaluation_config": self.evaluation_config,
            "timestamp": self.timestamp,
        }


class TextNormalizer:
    """Text normalization for WER/CER computation."""

    def __init__(
        self,
        lowercase: bool = True,
        remove_punctuation: bool = True,
        strip_whitespace: bool = True,
    ):
        self.lowercase = lowercase
        self.remove_punctuation = remove_punctuation
        self.strip_whitespace = strip_whitespace

    def __call__(self, text: str) -> str:
        if self.lowercase:
            text = text.lower()
        if self.remove_punctuation:
            # Use jiwer's default punctuation removal
            text = jiwer.RemovePunctuation()(text)
        if self.strip_whitespace:
            text = jiwer.Strip()(text)
            text = jiwer.RemoveMultipleSpaces()(text)
        return text


class SpeechEvaluator:
    """Evaluates Whisper models on test datasets."""

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self._manager: WhisperModelManager | None = None
        self._processor: WhisperProcessor | None = None
        self.normalizer = TextNormalizer(
            lowercase=config.lowercase,
            remove_punctuation=config.remove_punctuation,
            strip_whitespace=config.strip_whitespace,
        )

    def _get_manager(self) -> WhisperModelManager:
        if self._manager is None:
            model_config = WhisperModelConfig(
                model_name_or_path=self.config.model_name_or_path,
                language=self.config.language,
                task=self.config.task,
                device=self.config.device,
                torch_dtype=self.config.torch_dtype,
            )
            self._manager = WhisperModelManager(model_config)
            self._manager.load()
            self._processor = self._manager._processor
        return self._manager

    def evaluate_manifest(
        self,
        manifest_path: Path | None = None,
        entries: list[SpeechManifestEntry] | None = None,
    ) -> EvaluationResult:
        """Evaluate model on manifest entries."""
        if entries is None:
            if manifest_path is None:
                raise ValueError("Either manifest_path or entries must be provided")
            entries = load_manifest(manifest_path)
            manifest_path = Path(manifest_path)
        else:
            manifest_path = manifest_path or Path("unknown")

        manager = self._get_manager()
        audio_preprocessor = AudioPreprocessor(AudioConfig(**self.config.audio_config))
        base_dir = Path(self.config.data_base_dir) if self.config.data_base_dir else None

        samples = []
        wer_scores = []
        cer_scores = []

        logger.info(f"Evaluating {len(entries)} samples...")

        for i, entry in enumerate(entries):
            try:
                audio_path = Path(entry.audio_path)
                if base_dir and not audio_path.is_absolute():
                    audio_path = base_dir / audio_path

                audio_array = audio_preprocessor.preprocess_for_whisper(audio_path)
                result = manager.transcribe(audio_array, language=entry.language)

                hypothesis = result["text"]
                reference = entry.transcript

                # Normalize for metric computation
                if self.config.normalize_text:
                    hyp_norm = self.normalizer(hypothesis)
                    ref_norm = self.normalizer(reference)
                else:
                    hyp_norm = hypothesis
                    ref_norm = reference

                # Compute WER and CER
                wer = jiwer.wer(ref_norm, hyp_norm)
                cer = jiwer.cer(ref_norm, hyp_norm)

                # Get duration
                info = audio_preprocessor.get_audio_info(audio_path)
                duration = info.duration_seconds

                sample = SamplePrediction(
                    sample_id=entry.sample_id,
                    reference=reference,
                    hypothesis=hypothesis,
                    wer=wer,
                    cer=cer,
                    language=entry.language,
                    duration_seconds=duration,
                )
                samples.append(sample)
                wer_scores.append(wer)
                cer_scores.append(cer)

                if (i + 1) % 50 == 0:
                    logger.info(f"Processed {i + 1}/{len(entries)} samples")

            except Exception as e:
                logger.error(f"Failed to evaluate sample {entry.sample_id}: {e}")
                continue

        if not samples:
            raise ValueError("No samples were successfully evaluated")

        # Compute aggregate metrics
        wer_mean = float(np.mean(wer_scores))
        cer_mean = float(np.mean(cer_scores))
        wer_median = float(np.median(wer_scores))
        cer_median = float(np.median(cer_scores))

        # Dataset hash
        dataset_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest() if manifest_path.exists() else "unknown"

        result = EvaluationResult(
            model_name=self.config.model_name_or_path,
            model_path=self.config.model_name_or_path,
            dataset_manifest=str(manifest_path),
            dataset_hash=dataset_hash,
            num_samples=len(samples),
            wer=wer_mean,
            cer=cer_mean,
            wer_median=wer_median,
            cer_median=cer_median,
            samples=samples,
            evaluation_config=asdict(self.config),
        )

        return result

    def save_results(self, result: EvaluationResult, output_dir: Path | None = None) -> Path:
        """Save evaluation results to JSON and CSV."""
        out_dir = output_dir or Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = out_dir / f"evaluation_{result.model_name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Save CSV predictions
        if self.config.save_predictions:
            csv_path = json_path.with_suffix(".csv")
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["sample_id", "reference", "hypothesis", "wer", "cer", "language", "duration_seconds"])
                for s in result.samples:
                    writer.writerow([s.sample_id, s.reference, s.hypothesis, s.wer, s.cer, s.language, s.duration_seconds or ""])
            logger.info(f"Predictions saved to {csv_path}")

        logger.info(f"Evaluation results saved to {json_path}")
        return json_path


def compare_models(
    pretrained_result: EvaluationResult,
    finetuned_result: EvaluationResult,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Compare pretrained and fine-tuned model results."""
    comparison = {
        "pretrained": {
            "model": pretrained_result.model_name,
            "wer": pretrained_result.wer,
            "cer": pretrained_result.cer,
            "wer_median": pretrained_result.wer_median,
            "cer_median": pretrained_result.cer_median,
            "num_samples": pretrained_result.num_samples,
        },
        "finetuned": {
            "model": finetuned_result.model_name,
            "wer": finetuned_result.wer,
            "cer": finetuned_result.cer,
            "wer_median": finetuned_result.wer_median,
            "cer_median": finetuned_result.cer_median,
            "num_samples": finetuned_result.num_samples,
        },
        "difference": {
            "wer_delta": finetuned_result.wer - pretrained_result.wer,
            "cer_delta": finetuned_result.cer - pretrained_result.cer,
            "wer_improved": finetuned_result.wer < pretrained_result.wer,
            "cer_improved": finetuned_result.cer < pretrained_result.cer,
        },
        "per_sample": [],
    }

    # Per-sample comparison
    pretrained_dict = {s.sample_id: s for s in pretrained_result.samples}
    finetuned_dict = {s.sample_id: s for s in finetuned_result.samples}

    for sample_id in set(pretrained_dict.keys()) & set(finetuned_dict.keys()):
        p = pretrained_dict[sample_id]
        f = finetuned_dict[sample_id]
        comparison["per_sample"].append({
            "sample_id": sample_id,
            "pretrained_wer": p.wer,
            "finetuned_wer": f.wer,
            "wer_improvement": p.wer - f.wer,
            "pretrained_cer": p.cer,
            "finetuned_cer": f.cer,
            "cer_improvement": p.cer - f.cer,
        })

    # Save comparison
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        comp_path = output_dir / f"model_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        comp_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        logger.info(f"Model comparison saved to {comp_path}")

    return comparison


def evaluate_model(
    model_name_or_path: str,
    test_manifest: str,
    output_dir: str = "outputs/whisper-eval",
    **kwargs,
) -> EvaluationResult:
    """Convenience function to evaluate a model."""
    config = EvaluationConfig(
        model_name_or_path=model_name_or_path,
        test_manifest=test_manifest,
        output_dir=output_dir,
        **kwargs,
    )
    evaluator = SpeechEvaluator(config)
    result = evaluator.evaluate_manifest()
    evaluator.save_results(result)
    return result