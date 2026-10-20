import tempfile
from pathlib import Path
import soundfile as sf
import numpy as np

tmpdir = Path(tempfile.mkdtemp())
audio_dir = tmpdir / "audio"
audio_dir.mkdir()

# Create 3 test audio files
for i in range(3):
    data = np.random.randn(16000).astype(np.float32) * 0.1
    sf.write(str(audio_dir / f"{i}.wav"), data, 16000)

manifest_path = tmpdir / "manifest.jsonl"
with manifest_path.open("w") as f:
    for i in range(3):
        f.write(f'{{"sample_id": "{i}", "audio_path": "audio/{i}.wav", "transcript": "text {i}", "language": "en"}}\n')

print("Manifest:", manifest_path.read_text())

from app.ml.speech.dataset import load_manifest, validate_manifest

entries = load_manifest(manifest_path)
print(f"Loaded {len(entries)} entries")

result = validate_manifest(entries, base_dir=tmpdir)
print(f"Valid: {len(result.valid_entries)}")
print(f"Rejected: {len(result.rejected_entries)}")
for r in result.rejected_entries:
    print(f"  Rejected {r['sample_id']}: {r['reasons']}")

if result.valid_entries:
    from app.ml.speech.dataset import generate_dataset_statistics
    stats = generate_dataset_statistics(result.valid_entries)
    print("Stats:", stats)
else:
    print("No valid entries!")