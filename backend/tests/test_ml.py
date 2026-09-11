from uuid import uuid4

from app.ml.datasets import subject_level_split
from app.ml.features import extract_session_features
from app.ml.models import LogisticBaseline, RandomForestBaseline, GradientBoostingBaseline
from app.ml.profile import build_profile


def test_subject_level_split_prevents_leakage() -> None:
    rows = [{"subject_id": subject, "session_id": f"session-{index}", "features": {"accuracy": float(index)}, "target": index % 2} for index, subject in enumerate(["a", "a", "b", "b", "c", "c", "d", "d", "e", "e"])]
    split = subject_level_split(rows, seed=42)
    groups = [{row["subject_id"] for row in split[name]} for name in ("train", "validation", "test")]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])


def test_baselines_require_real_class_labels() -> None:
    model = LogisticBaseline(["accuracy"])
    rows = [{"features": {"accuracy": .5}}]
    try:
        model.fit(rows, [1])
    except ValueError as error:
        assert "validated target classes" in str(error)
    else:
        raise AssertionError("single-class training must be rejected")


def test_profile_uses_observed_language_only() -> None:
    profile = build_profile(str(uuid4()), {"overall_accuracy": {"value": .7, "available": True, "domain": "accuracy", "source": "behavior"}}, {"feature_count": 1})
    assert profile["model"]["status"] == "unavailable"
    assert all("diagnos" not in item.lower() for item in profile["observations"])
    assert profile["limitations"]
