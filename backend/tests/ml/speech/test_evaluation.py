"""Tests for WER/CER evaluation."""

from __future__ import annotations

import pytest

from app.ml.speech.evaluation import TextNormalizer, SpeechEvaluator, EvaluationConfig, compare_models
from app.ml.speech.dataset import SpeechManifestEntry


class TestTextNormalizer:
    def test_lowercase(self):
        normalizer = TextNormalizer(lowercase=True, remove_punctuation=False)
        assert normalizer("HELLO WORLD") == "hello world"

    def test_remove_punctuation(self):
        normalizer = TextNormalizer(lowercase=False, remove_punctuation=True)
        assert normalizer("Hello, world!") == "Hello world"

    def test_strip_whitespace(self):
        normalizer = TextNormalizer(strip_whitespace=True)
        assert normalizer("  hello   world  ") == "hello world"

    def test_full_normalization(self):
        normalizer = TextNormalizer(lowercase=True, remove_punctuation=True, strip_whitespace=True)
        assert normalizer("  Hello, WORLD!  ") == "hello world"


class TestSpeechEvaluator:
    def test_wer_cer_calculation(self):
        # Test known WER/CER values
        reference = "the cat sat on the mat"
        hypothesis = "the cat sat on a mat"

        evaluator = SpeechEvaluator(EvaluationConfig(normalize_text=True))
        ref_norm = evaluator.normalizer(reference)
        hyp_norm = evaluator.normalizer(hypothesis)

        import jiwer
        wer_score = jiwer.wer(ref_norm, hyp_norm)
        cer_score = jiwer.cer(ref_norm, hyp_norm)

        # "the cat sat on the mat" vs "the cat sat on a mat"
        # Substitution: "the" -> "a" (1 sub out of 6 words = 0.167)
        assert wer_score == pytest.approx(1/6, rel=0.1)
        # CER: more character differences
        assert cer_score > 0

    def test_perfect_match(self):
        import jiwer
        normalizer = TextNormalizer(lowercase=True, remove_punctuation=True)
        ref = normalizer("hello world")
        hyp = normalizer("hello world")
        assert jiwer.wer(ref, hyp) == 0.0
        assert jiwer.cer(ref, hyp) == 0.0

    def test_non_empty_strings(self):
        import jiwer
        normalizer = TextNormalizer()
        # jiwer doesn't support empty strings, test with minimal content
        assert jiwer.wer("a", "a") == 0.0
        assert jiwer.cer("a", "a") == 0.0
        assert jiwer.wer("hello", "world") == 1.0
        assert jiwer.wer("a", "b") == 1.0


class TestCompareModels:
    def test_compare_identical(self):
        from app.ml.speech.evaluation import EvaluationResult, SamplePrediction

        samples = [
            SamplePrediction("1", "hello world", "hello world", 0.0, 0.0, "en"),
            SamplePrediction("2", "test", "test", 0.0, 0.0, "en"),
        ]
        result1 = EvaluationResult(
            model_name="model-a",
            model_path="model-a",
            dataset_manifest="test.jsonl",
            dataset_hash="hash1",
            num_samples=2,
            wer=0.0,
            cer=0.0,
            wer_median=0.0,
            cer_median=0.0,
            samples=samples,
            evaluation_config={},
        )
        result2 = EvaluationResult(
            model_name="model-b",
            model_path="model-b",
            dataset_manifest="test.jsonl",
            dataset_hash="hash1",
            num_samples=2,
            wer=0.0,
            cer=0.0,
            wer_median=0.0,
            cer_median=0.0,
            samples=samples,
            evaluation_config={},
        )

        comparison = compare_models(result1, result2)
        assert comparison["difference"]["wer_delta"] == 0.0
        assert comparison["difference"]["cer_delta"] == 0.0
        assert comparison["difference"]["wer_improved"] is False
        assert comparison["difference"]["cer_improved"] is False

    def test_compare_improved(self):
        from app.ml.speech.evaluation import EvaluationResult, SamplePrediction

        samples_pre = [
            SamplePrediction("1", "hello world", "hello world", 0.0, 0.0, "en"),
            SamplePrediction("2", "test case", "wrong case", 1.0, 0.5, "en"),
        ]
        samples_ft = [
            SamplePrediction("1", "hello world", "hello world", 0.0, 0.0, "en"),
            SamplePrediction("2", "test case", "test case", 0.0, 0.0, "en"),
        ]
        result_pre = EvaluationResult(
            model_name="pretrained",
            model_path="pretrained",
            dataset_manifest="test.jsonl",
            dataset_hash="hash1",
            num_samples=2,
            wer=0.5,
            cer=0.25,
            wer_median=0.5,
            cer_median=0.25,
            samples=samples_pre,
            evaluation_config={},
        )
        result_ft = EvaluationResult(
            model_name="finetuned",
            model_path="finetuned",
            dataset_manifest="test.jsonl",
            dataset_hash="hash1",
            num_samples=2,
            wer=0.0,
            cer=0.0,
            wer_median=0.0,
            cer_median=0.0,
            samples=samples_ft,
            evaluation_config={},
        )

        comparison = compare_models(result_pre, result_ft)
        assert comparison["difference"]["wer_delta"] < 0  # Improved (lower WER)
        assert comparison["difference"]["wer_improved"] is True
        assert comparison["difference"]["cer_improved"] is True


class TestEvaluationConfig:
    def test_default_config(self):
        config = EvaluationConfig(model_name_or_path="openai/whisper-tiny")
        assert config.model_name_or_path == "openai/whisper-tiny"
        assert config.language == "en"
        assert config.batch_size == 8
        assert config.normalize_text is True

    def test_custom_config(self):
        config = EvaluationConfig(
            model_name_or_path="my-model",
            language="ta",
            batch_size=16,
            normalize_text=False,
        )
        assert config.model_name_or_path == "my-model"
        assert config.language == "ta"
        assert config.batch_size == 16
        assert config.normalize_text is False