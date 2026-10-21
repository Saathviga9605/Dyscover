"""Tests for speech ML CLI commands."""

from __future__ import annotations

import pytest

# Optional offline stack (requirements-speech-ml.txt); skipped, not failed, without it.
for _name in ("torch", "soundfile", "transformers", "jiwer"):
    pytest.importorskip(_name, reason="optional speech-ML stack not installed: pip install -r requirements-speech-ml.txt")

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.ml.speech.cli import main as cli_main


class TestCLI:
    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run CLI command and return exit code, stdout, stderr."""
        import sys
        from io import StringIO

        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.argv = ["cli"] + args
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            exit_code = cli_main()
            stdout = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
        except SystemExit as e:
            exit_code = e.code
            stdout = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        return exit_code, stdout, stderr

    def test_validate_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["validate", "--help"])
        assert exit_code == 0
        assert "manifest" in stdout.lower()

    def test_split_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["split", "--help"])
        assert exit_code == 0
        assert "manifest" in stdout.lower()

    def test_train_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["train", "--help"])
        assert exit_code == 0
        assert "model" in stdout.lower()

    def test_evaluate_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["evaluate", "--help"])
        assert exit_code == 0
        assert "model" in stdout.lower()

    def test_compare_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["compare", "--help"])
        assert exit_code == 0
        assert "pretrained-model" in stdout.lower()

    def test_create_experiment_help(self):
        exit_code, stdout, stderr = self.run_cli(["create-experiment", "--help"])
        assert exit_code == 0
        assert "name" in stdout.lower()

    def test_run_experiment_help(self):
        exit_code, stdout, stderr = self.run_cli(["run-experiment", "--help"])
        assert exit_code == 0
        assert "config" in stdout.lower()


class TestCLI:
    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run CLI command and return exit code, stdout, stderr."""
        import sys
        from io import StringIO

        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.argv = ["cli"] + args
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            exit_code = cli_main()
            stdout = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
        except SystemExit as e:
            exit_code = e.code
            stdout = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        return exit_code, stdout, stderr

    def _create_valid_wav(self, path: Path, duration: float = 1.0, sample_rate: int = 16000):
        """Create a valid WAV file using soundfile."""
        num_samples = int(duration * sample_rate)
        data = np.random.randn(num_samples).astype(np.float32) * 0.1
        sf.write(str(path), data, sample_rate)

    def test_validate_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["validate", "--help"])
        assert exit_code == 0
        assert "manifest" in stdout.lower()

    def test_split_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["split", "--help"])
        assert exit_code == 0
        assert "manifest" in stdout.lower()

    def test_train_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["train", "--help"])
        assert exit_code == 0
        assert "model" in stdout.lower()

    def test_evaluate_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["evaluate", "--help"])
        assert exit_code == 0
        assert "model" in stdout.lower()

    def test_compare_command_help(self):
        exit_code, stdout, stderr = self.run_cli(["compare", "--help"])
        assert exit_code == 0
        assert "pretrained-model" in stdout.lower()

    def test_create_experiment_help(self):
        exit_code, stdout, stderr = self.run_cli(["create-experiment", "--help"])
        assert exit_code == 0
        assert "name" in stdout.lower()

    def test_run_experiment_help(self):
        exit_code, stdout, stderr = self.run_cli(["run-experiment", "--help"])
        assert exit_code == 0
        assert "config" in stdout.lower()


class TestValidateCLI(TestCLI):
    def test_validate_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manifest
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            with manifest_path.open("w") as f:
                f.write('{"sample_id": "1", "audio_path": "audio/1.wav", "transcript": "hello", "language": "en"}\n')
                f.write('{"sample_id": "2", "audio_path": "audio/2.wav", "transcript": "world", "language": "en"}\n')

            # Create dummy audio files
            audio_dir = Path(tmpdir) / "audio"
            audio_dir.mkdir()
            self._create_valid_wav(audio_dir / "1.wav")
            self._create_valid_wav(audio_dir / "2.wav")

            exit_code, stdout, stderr = self.run_cli(["validate", "--manifest", str(manifest_path), "--base-dir", tmpdir])
            assert exit_code == 0
            assert "Valid: 2" in stdout
            assert "Rejected: 0" in stdout

    def test_validate_rejects_empty_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            with manifest_path.open("w") as f:
                f.write('{"sample_id": "1", "audio_path": "audio/1.wav", "transcript": "", "language": "en"}\n')

            # Create dummy audio
            audio_dir = Path(tmpdir) / "audio"
            audio_dir.mkdir()
            self._create_valid_wav(audio_dir / "1.wav")

            exit_code, stdout, stderr = self.run_cli(["validate", "--manifest", str(manifest_path), "--base-dir", tmpdir])
            assert exit_code != 0
            assert "Rejected: 1" in stdout

            # Check the report file for rejection reason
            report_path = manifest_path.with_suffix(".validation.json")
            assert report_path.exists()
            import json
            with report_path.open() as f:
                report = json.load(f)
            assert len(report["rejected_details"]) == 1
            assert "Empty transcript" in report["rejected_details"][0]["reasons"][0]


class TestSplitCLI(TestCLI):
    def test_split_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create audio directory and valid files
            audio_dir = Path(tmpdir) / "audio"
            audio_dir.mkdir()
            for i in range(20):
                self._create_valid_wav(audio_dir / f"{i}.wav")

            manifest_path = Path(tmpdir) / "manifest.jsonl"
            with manifest_path.open("w") as f:
                for i in range(20):
                    f.write(f'{{"sample_id": "{i}", "audio_path": "audio/{i}.wav", "transcript": "text {i}", "language": "en"}}\n')

            output_dir = Path(tmpdir) / "splits"
            exit_code, stdout, stderr = self.run_cli([
                "split",
                "--manifest", str(manifest_path),
                "--output-dir", str(output_dir),
                "--seed", "42",
                "--base-dir", tmpdir,
            ])
            assert exit_code == 0

            # Check split files exist
            assert (output_dir / "manifest_train.jsonl").exists()
            assert (output_dir / "manifest_validation.jsonl").exists()
            assert (output_dir / "manifest_test.jsonl").exists()
            assert (output_dir / "dataset_config.json").exists()

    def test_split_speaker_aware(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create audio directory and valid files
            audio_dir = Path(tmpdir) / "audio"
            audio_dir.mkdir()
            for spk in range(5):
                for i in range(4):
                    self._create_valid_wav(audio_dir / f"spk{spk}-{i}.wav")

            manifest_path = Path(tmpdir) / "manifest.jsonl"
            with manifest_path.open("w") as f:
                for spk in range(5):
                    for i in range(4):
                        f.write(f'{{"sample_id": "spk{spk}-{i}", "audio_path": "audio/spk{spk}-{i}.wav", "transcript": "text", "language": "en", "speaker_id": "spk{spk}"}}\n')

            output_dir = Path(tmpdir) / "splits"
            exit_code, stdout, stderr = self.run_cli([
                "split",
                "--manifest", str(manifest_path),
                "--output-dir", str(output_dir),
                "--seed", "42",
                "--speaker-aware",
                "--base-dir", tmpdir,
            ])
            assert exit_code == 0


class TestStatsCLI(TestCLI):
    def test_stats_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            with manifest_path.open("w") as f:
                f.write('{"sample_id": "1", "audio_path": "a.wav", "transcript": "hello world", "language": "en", "duration_seconds": 2.0}\n')
                f.write('{"sample_id": "2", "audio_path": "b.wav", "transcript": "test", "language": "ta", "duration_seconds": 3.0}\n')

            exit_code, stdout, stderr = self.run_cli(["stats", "--manifest", str(manifest_path)])
            assert exit_code == 0
            data = json.loads(stdout)
            assert data["total_samples"] == 2
            assert data["languages"]["en"] == 1
            assert data["languages"]["ta"] == 1