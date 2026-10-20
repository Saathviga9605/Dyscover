import tempfile
from pathlib import Path
import soundfile as sf
import numpy as np

tmpdir = Path(tempfile.mkdtemp())
audio_dir = tmpdir / "audio"
audio_dir.mkdir()

# Create 5 test audio files
for i in range(5):
    data = np.random.randn(16000).astype(np.float32) * 0.1
    sf.write(str(audio_dir / f"{i}.wav"), data, 16000)

manifest_path = tmpdir / "manifest.jsonl"
with manifest_path.open("w") as f:
    for i in range(5):
        f.write(f'{{"sample_id": "{i}", "audio_path": "audio/{i}.wav", "transcript": "text {i}", "language": "en"}}\n')

print("Testing split command logic...")

from app.ml.speech.dataset import load_manifest, validate_manifest, create_splits, generate_dataset_statistics

entries = load_manifest(manifest_path)
print(f"Loaded {len(entries)} entries")

result = validate_manifest(entries, base_dir=tmpdir)
print(f"Valid: {len(result.valid_entries)}")
print(f"Rejected: {len(result.rejected_entries)}")

if result.valid_entries:
    splits = create_splits(result.valid_entries, seed=42, speaker_aware=False)
    for split_name, split_entries in splits.items():
        print(f"\n{split_name.capitalize()} split:")
        stats = generate_dataset_statistics(split_entries)
        print(f"  Samples: {stats['total_samples']}")
        print(f"  Languages: {stats['languages']}")
else:
    print("No valid entries!")