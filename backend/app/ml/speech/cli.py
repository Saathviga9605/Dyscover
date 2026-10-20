"""CLI commands for speech ML pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .dataset import (
    SpeechManifestEntry,
    load_manifest,
    validate_manifest,
    create_splits,
    generate_dataset_statistics,
    save_splits,
    save_validation_report,
    save_dataset_config,
)
from .audio import AudioPreprocessor, AudioConfig
from .training import WhisperFineTuneConfig, run_finetune
from .evaluation import EvaluationConfig, evaluate_model
from .experiment import (
    SpeechExperimentConfig,
    create_experiment_config,
    generate_experiment_report,
    SpeechModelRegistry,
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a speech dataset manifest."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return 1

    base_dir = Path(args.base_dir) if args.base_dir else None

    entries = load_manifest(manifest_path)
    logger.info(f"Loaded {len(entries)} entries from {manifest_path}")

    result = validate_manifest(
        entries,
        base_dir=base_dir,
        max_duration_seconds=args.max_duration,
        min_duration_seconds=args.min_duration,
    )

    # Save report
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = manifest_path.with_suffix(".validation.json")

    save_validation_report(result, report_path)
    logger.info(f"Validation report saved to {report_path}")

    # Print summary
    print(f"Valid: {result.to_report()['valid_count']}")
    print(f"Rejected: {result.to_report()['rejected_count']}")
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f"  - {e}")

    return 0 if result.to_report()['rejected_count'] == 0 else 1


def cmd_split(args: argparse.Namespace) -> int:
    """Create train/validation/test splits from manifest."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return 1

    output_dir = Path(args.output_dir)
    base_dir = Path(args.base_dir) if args.base_dir else None

    entries = load_manifest(manifest_path)
    logger.info(f"Loaded {len(entries)} entries")

    # Validate first
    result = validate_manifest(entries, base_dir=base_dir)
    if result.rejected_entries:
        logger.warning(f"{len(result.rejected_entries)} entries will be excluded from splits")
        if not args.force:
            logger.error("Use --force to split anyway")
            return 1

    valid_entries = result.valid_entries

    # Create splits
    splits = create_splits(
        valid_entries,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        speaker_aware=args.speaker_aware,
    )

    # Save splits
    saved = save_splits(splits, output_dir, manifest_path.stem)
    for split_name, path in saved.items():
        logger.info(f"Saved {split_name}: {len(splits[split_name])} samples -> {path}")

    # Save config
    config_path = save_dataset_config(
        output_dir,
        manifest_path,
        args.seed,
        args.train_ratio,
        args.val_ratio,
        args.test_ratio,
        args.speaker_aware,
        base_dir,
    )
    logger.info(f"Dataset config saved to {config_path}")

    # Print statistics
    for split_name, split_entries in splits.items():
        stats = generate_dataset_statistics(split_entries)
        print(f"\n{split_name.capitalize()} split:")
        print(f"  Samples: {stats['total_samples']}")
        if stats.get('total_duration_seconds', 0) > 0:
            print(f"  Duration: {stats['total_duration_seconds']:.1f}s")
        if stats.get('languages'):
            print(f"  Languages: {stats['languages']}")

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Generate dataset statistics."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return 1

    entries = load_manifest(manifest_path)
    stats = generate_dataset_statistics(entries)

    print(json.dumps(stats, indent=2))
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    """Fine-tune Whisper model."""
    if args.config:
        # Load from experiment config
        exp_config = SpeechExperimentConfig.load(Path(args.config))
        if exp_config.training_config is None:
            logger.error("Experiment config has no training configuration")
            return 1
        train_config = exp_config.training_config
    else:
        # Create config from args
        train_config = WhisperFineTuneConfig(
            base_model=args.model,
            language=args.language,
            train_manifest=args.train_manifest,
            validation_manifest=args.val_manifest,
            test_manifest=args.test_manifest,
            output_dir=args.output_dir,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            learning_rate=args.lr,
            warmup_steps=args.warmup,
            weight_decay=args.weight_decay,
            gradient_accumulation_steps=args.grad_accum,
            fp16=args.fp16,
            bf16=args.bf16,
            gradient_checkpointing=args.grad_checkpoint,
            seed=args.seed,
            max_steps=args.max_steps,
            save_steps=args.save_steps,
            eval_steps=args.eval_steps,
            logging_steps=args.logging_steps,
        )

    logger.info(f"Starting fine-tuning: {train_config.base_model}")
    logger.info(f"Output directory: {train_config.output_dir}")

    result = run_finetune(train_config)
    logger.info("Training completed successfully")
    logger.info(f"Model saved to: {result['model_path']}")

    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate a model on test data."""
    if args.config:
        exp_config = SpeechExperimentConfig.load(Path(args.config))
        if exp_config.evaluation_config is None:
            logger.error("Experiment config has no evaluation configuration")
            return 1
        eval_config = exp_config.evaluation_config
        # If model path specified, use it
        if args.model:
            eval_config.model_name_or_path = args.model
    else:
        eval_config = EvaluationConfig(
            model_name_or_path=args.model,
            language=args.language,
            test_manifest=args.test_manifest,
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            max_length=args.max_length,
            num_beams=args.num_beams,
            normalize_text=not args.no_normalize,
            remove_punctuation=not args.keep_punctuation,
            lowercase=not args.keep_case,
        )

    logger.info(f"Evaluating model: {eval_config.model_name_or_path}")

    result = evaluate_model(
        model_name_or_path=eval_config.model_name_or_path,
        test_manifest=eval_config.test_manifest,
        output_dir=eval_config.output_dir,
        language=eval_config.language,
        batch_size=eval_config.batch_size,
        max_length=eval_config.max_length,
        num_beams=eval_config.num_beams,
        normalize_text=eval_config.normalize_text,
        remove_punctuation=eval_config.remove_punctuation,
        lowercase=eval_config.lowercase,
        data_base_dir=eval_config.data_base_dir,
    )

    print(f"\nEvaluation Results:")
    print(f"  Model: {result.model_name}")
    print(f"  Samples: {result.num_samples}")
    print(f"  WER: {result.wer:.4f} ({result.wer:.2%})")
    print(f"  CER: {result.cer:.4f} ({result.cer:.2%})")
    print(f"  WER Median: {result.wer_median:.4f}")
    print(f"  CER Median: {result.cer_median:.4f}")

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare pretrained and fine-tuned models."""
    from .evaluation import SpeechEvaluator, compare_models

    # Evaluate pretrained
    pretrained_config = EvaluationConfig(
        model_name_or_path=args.pretrained_model,
        language=args.language,
        test_manifest=args.test_manifest,
        output_dir=args.output_dir,
    )
    pretrained_eval = SpeechEvaluator(pretrained_config)
    pretrained_result = pretrained_eval.evaluate_manifest()

    # Evaluate fine-tuned
    finetuned_config = EvaluationConfig(
        model_name_or_path=args.finetuned_model,
        language=args.language,
        test_manifest=args.test_manifest,
        output_dir=args.output_dir,
    )
    finetuned_eval = SpeechEvaluator(finetuned_config)
    finetuned_result = finetuned_eval.evaluate_manifest()

    # Compare
    comparison = compare_models(pretrained_result, finetuned_result, Path(args.output_dir))

    print("\nModel Comparison:")
    print(f"  Pretrained WER: {comparison['pretrained']['wer']:.4f}")
    print(f"  Fine-tuned WER: {comparison['finetuned']['wer']:.4f}")
    print(f"  WER Delta: {comparison['difference']['wer_delta']:.4f}")
    print(f"  WER Improved: {comparison['difference']['wer_improved']}")
    print(f"  Pretrained CER: {comparison['pretrained']['cer']:.4f}")
    print(f"  Fine-tuned CER: {comparison['finetuned']['cer']:.4f}")
    print(f"  CER Delta: {comparison['difference']['cer_delta']:.4f}")
    print(f"  CER Improved: {comparison['difference']['cer_improved']}")

    return 0


def cmd_create_experiment(args: argparse.Namespace) -> int:
    """Create experiment configuration."""
    config = create_experiment_config(
        experiment_name=args.name,
        base_model=args.model,
        dataset_manifest=args.manifest,
        language=args.language,
        output_dir=args.output_dir,
    )

    config_path = Path(config.output_dir) / "experiment_config.json"
    config.save(config_path)
    logger.info(f"Experiment config saved to {config_path}")

    # Generate report
    report = generate_experiment_report(config)
    report_path = Path(config.output_dir) / "experiment_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Experiment report saved to {report_path}")

    print(f"Experiment created: {config.experiment_id}")
    print(f"Config: {config_path}")
    print(f"Report: {report_path}")

    return 0


def cmd_run_experiment(args: argparse.Namespace) -> int:
    """Run a complete experiment (train + evaluate)."""
    exp_config = SpeechExperimentConfig.load(Path(args.config))
    exp_config.status = "training"
    exp_config.started_at = datetime.now(timezone.utc).isoformat()
    exp_config.save(Path(args.config))

    # Train
    if exp_config.training_config:
        logger.info("Starting training phase...")
        result = run_finetune(exp_config.training_config)
        exp_config.training_status = "completed"
        exp_config.model_checkpoint_path = result['model_path']
    else:
        logger.error("No training configuration in experiment")
        return 1

    exp_config.status = "evaluating"
    exp_config.save(Path(args.config))

    # Evaluate
    if exp_config.evaluation_config:
        logger.info("Starting evaluation phase...")
        # Update evaluation config to use trained model
        exp_config.evaluation_config.model_name_or_path = exp_config.model_checkpoint_path
        eval_result = evaluate_model(
            model_name_or_path=exp_config.model_checkpoint_path,
            test_manifest=exp_config.evaluation_config.test_manifest,
            output_dir=exp_config.evaluation_config.output_dir,
            language=exp_config.evaluation_config.language,
        )
        exp_config.evaluation_status = "completed"
        exp_config.evaluation_result_path = str(Path(exp_config.evaluation_config.output_dir) / "*.json")
    else:
        logger.error("No evaluation configuration in experiment")
        return 1

    exp_config.status = "completed"
    exp_config.completed_at = datetime.now(timezone.utc).isoformat()
    exp_config.save(Path(args.config))

    # Generate final report
    report = generate_experiment_report(exp_config, eval_result)
    report_path = Path(exp_config.output_dir) / "experiment_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Final report saved to {report_path}")

    return 0


from datetime import timezone  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Dyscover Speech ML Pipeline")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate dataset manifest")
    p_validate.add_argument("--manifest", required=True, help="Path to manifest.jsonl or manifest.csv")
    p_validate.add_argument("--base-dir", help="Base directory for audio paths")
    p_validate.add_argument("--max-duration", type=float, default=30.0, help="Max audio duration (seconds)")
    p_validate.add_argument("--min-duration", type=float, default=0.5, help="Min audio duration (seconds)")
    p_validate.add_argument("--report", help="Output validation report path")
    p_validate.set_defaults(func=cmd_validate)

    # split
    p_split = subparsers.add_parser("split", help="Create train/val/test splits")
    p_split.add_argument("--manifest", required=True, help="Path to manifest.jsonl or manifest.csv")
    p_split.add_argument("--output-dir", required=True, help="Output directory for splits")
    p_split.add_argument("--base-dir", help="Base directory for audio paths")
    p_split.add_argument("--seed", type=int, default=42, help="Random seed")
    p_split.add_argument("--train-ratio", type=float, default=0.7, help="Train ratio")
    p_split.add_argument("--val-ratio", type=float, default=0.15, help="Validation ratio")
    p_split.add_argument("--test-ratio", type=float, default=0.15, help="Test ratio")
    p_split.add_argument("--speaker-aware", action="store_true", default=True, help="Speaker-aware splitting")
    p_split.add_argument("--no-speaker-aware", action="store_false", dest="speaker_aware", help="Disable speaker-aware splitting")
    p_split.add_argument("--force", action="store_true", help="Split even with rejected entries")
    p_split.set_defaults(func=cmd_split)

    # stats
    p_stats = subparsers.add_parser("stats", help="Generate dataset statistics")
    p_stats.add_argument("--manifest", required=True, help="Path to manifest.jsonl or manifest.csv")
    p_stats.set_defaults(func=cmd_stats)

    # train
    p_train = subparsers.add_parser("train", help="Fine-tune Whisper model")
    p_train.add_argument("--config", help="Experiment config JSON")
    p_train.add_argument("--model", default="openai/whisper-tiny", help="Base model")
    p_train.add_argument("--language", default="en", help="Language code")
    p_train.add_argument("--train-manifest", required=False, help="Train manifest")
    p_train.add_argument("--val-manifest", required=False, help="Validation manifest")
    p_train.add_argument("--test-manifest", required=False, help="Test manifest")
    p_train.add_argument("--output-dir", default="outputs/whisper-finetune", help="Output directory")
    p_train.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    p_train.add_argument("--batch-size", type=int, default=4, help="Train batch size")
    p_train.add_argument("--lr", type=float, default=1e-5, help="Learning rate")
    p_train.add_argument("--warmup", type=int, default=100, help="Warmup steps")
    p_train.add_argument("--weight-decay", type=float, default=0.01, help="Weight decay")
    p_train.add_argument("--grad-accum", type=int, default=2, help="Gradient accumulation steps")
    p_train.add_argument("--fp16", action="store_true", help="Use FP16")
    p_train.add_argument("--bf16", action="store_true", help="Use BF16")
    p_train.add_argument("--grad-checkpoint", action="store_true", default=True, help="Gradient checkpointing")
    p_train.add_argument("--seed", type=int, default=42, help="Random seed")
    p_train.add_argument("--max-steps", type=int, default=-1, help="Max training steps")
    p_train.add_argument("--save-steps", type=int, default=500, help="Save steps")
    p_train.add_argument("--eval-steps", type=int, default=500, help="Eval steps")
    p_train.add_argument("--logging-steps", type=int, default=50, help="Logging steps")
    p_train.set_defaults(func=cmd_train)

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Evaluate model on test set")
    p_eval.add_argument("--config", help="Experiment config JSON")
    p_eval.add_argument("--model", required=False, help="Model path or name")
    p_eval.add_argument("--language", default="en", help="Language code")
    p_eval.add_argument("--test-manifest", required=False, help="Test manifest")
    p_eval.add_argument("--output-dir", default="outputs/whisper-eval", help="Output directory")
    p_eval.add_argument("--batch-size", type=int, default=8, help="Batch size")
    p_eval.add_argument("--max-length", type=int, default=448, help="Max generation length")
    p_eval.add_argument("--num-beams", type=int, default=5, help="Number of beams")
    p_eval.add_argument("--no-normalize", action="store_true", help="Disable text normalization")
    p_eval.add_argument("--keep-punctuation", action="store_true", help="Keep punctuation")
    p_eval.add_argument("--keep-case", action="store_true", help="Keep case")
    p_eval.set_defaults(func=cmd_evaluate)

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare pretrained and fine-tuned models")
    p_compare.add_argument("--pretrained-model", required=True, help="Pretrained model path")
    p_compare.add_argument("--finetuned-model", required=True, help="Fine-tuned model path")
    p_compare.add_argument("--test-manifest", required=True, help="Test manifest")
    p_compare.add_argument("--language", default="en", help="Language code")
    p_compare.add_argument("--output-dir", default="outputs/whisper-eval", help="Output directory")
    p_compare.set_defaults(func=cmd_compare)

    # create-experiment
    p_create = subparsers.add_parser("create-experiment", help="Create experiment configuration")
    p_create.add_argument("--name", required=True, help="Experiment name")
    p_create.add_argument("--model", default="openai/whisper-tiny", help="Base model")
    p_create.add_argument("--manifest", required=True, help="Dataset manifest")
    p_create.add_argument("--language", default="en", help="Language code")
    p_create.add_argument("--output-dir", default="outputs/speech_experiments", help="Output directory")
    p_create.set_defaults(func=cmd_create_experiment)

    # run-experiment
    p_run = subparsers.add_parser("run-experiment", help="Run complete experiment")
    p_run.add_argument("--config", required=True, help="Experiment config JSON")
    p_run.set_defaults(func=cmd_run_experiment)

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        return args.func(args)
    except Exception as e:
        logger.exception(f"Command failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())