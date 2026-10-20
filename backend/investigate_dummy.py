from app.ml.synthetic import SyntheticConfig, generate_dataset, train_synthetic_models
from pathlib import Path
import tempfile
from collections import Counter

# Generate a small dataset
config = SyntheticConfig(seed=42, subjects=20, sessions_per_subject=2)
dataset = generate_dataset(config)

print(f'Dataset size: {len(dataset["rows"])} rows')
print(f'Subjects: {dataset["metadata"]["subjects"]}')
print(f'Sessions: {dataset["metadata"]["sessions"]}')

# Check target distribution
targets = [r['target'] for r in dataset['rows']]
print(f'Target distribution: {Counter(targets)}')

# Check eligible subjects
eligible = [r for r in dataset['rows'] if r['eligible']]
print(f'Eligible rows: {len(eligible)}')
eligible_targets = [r['target'] for r in eligible]
print(f'Eligible target distribution: {Counter(eligible_targets)}')

# Train models
with tempfile.TemporaryDirectory() as tmpdir:
    results = train_synthetic_models(dataset, Path(tmpdir) / 'models', algorithms=('dummy', 'logistic_regression', 'random_forest', 'gradient_boosting'))
    for algo, result in results.items():
        print(f'{algo}: test_accuracy = {result["evaluation"]["test_metrics"].get("accuracy", "N/A")}')