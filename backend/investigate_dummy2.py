from app.ml.synthetic import SyntheticConfig, generate_dataset, train_synthetic_models
from app.ml.synthetic.pipeline import train_synthetic_models
from app.ml.datasets import subject_level_split
from pathlib import Path
import tempfile
from collections import Counter

# Generate a small dataset
config = SyntheticConfig(seed=42, subjects=20, sessions_per_subject=2)
dataset = generate_dataset(config)

# Check the split
split = subject_level_split(dataset['rows'], seed=42)

print("Train subjects:", len(split['train']))
print("Val subjects:", len(split['validation']))
print("Test subjects:", len(split['test']))

# Check class distribution in each split
train_targets = [r['target'] for r in split['train']]
val_targets = [r['target'] for r in split['validation']]
test_targets = [r['target'] for r in split['test']]

print(f"Train distribution: {Counter(train_targets)}")
print(f"Val distribution: {Counter(val_targets)}")
print(f"Test distribution: {Counter(test_targets)}")

# Check what DummyClassifier would predict
# DummyClassifier with strategy="prior" predicts the majority class from training
majority_class = Counter(train_targets).most_common(1)[0][0]
print(f"Majority class in training: {majority_class}")

# Accuracy on test set if always predicting majority class
test_accuracy = sum(1 for t in test_targets if t == majority_class) / len(test_targets)
print(f"DummyClassifier accuracy on test set: {test_accuracy}")

# Also check validation
val_accuracy = sum(1 for t in val_targets if t == majority_class) / len(val_targets)
print(f"DummyClassifier accuracy on val set: {val_accuracy}")

# The issue: subject-level split means test set may have different class distribution
# DummyClassifier learns from training but test has different distribution