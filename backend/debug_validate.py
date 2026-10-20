import tempfile
from pathlib import Path
import soundfile as sf
import numpy as np

tmpdir = Path(tempfile.mkdtemp())
audio_dir = tmpdir / 'audio'
audio_dir.mkdir()
data = np.random.randn(16000).astype(np.float32) * 0.1
sf.write(str(audio_dir / '1.wav'), data, 16000)

manifest = tmpdir / 'manifest.jsonl'
with manifest.open('w') as f:
    f.write('{"sample_id": "1", "audio_path": "audio/1.wav", "transcript": "hello", "language": "en"}\n')

print('tmpdir:', tmpdir)
print('audio exists:', (audio_dir / '1.wav').exists())
print('manifest:', manifest.read_text())

# Now test validate
from app.ml.speech.dataset import load_manifest, validate_manifest

entries = load_manifest(manifest)
print('Loaded entries:', len(entries))
result = validate_manifest(entries, base_dir=tmpdir)
print('Valid:', len(result.valid_entries))
print('Rejected:', len(result.rejected_entries))
if result.rejected_entries:
    print('Reasons:', result.rejected_entries[0]['reasons'])