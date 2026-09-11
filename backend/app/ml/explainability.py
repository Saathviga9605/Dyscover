from typing import Any


def observed_explanations(features: dict[str, dict[str, Any]]) -> list[str]:
    explanations: list[str] = []
    accuracy = features.get("overall_accuracy", {})
    timing = features.get("mean_reaction_time_ms", {})
    errors = features.get("total_error_count", {})
    if accuracy.get("available"): explanations.append("Overall activity accuracy was recorded across completed trials.")
    if timing.get("available"): explanations.append("Response timing was recorded where the activity provided it.")
    if errors.get("available") and errors.get("value", 0) > 0: explanations.append("Some trial errors were recorded; errors can reflect many situational factors.")
    return explanations


def feature_importance(model: Any, feature_names: list[str]) -> list[dict[str, Any]]:
    estimator = getattr(model, "named_steps", {}).get("model", model)
    if hasattr(estimator, "feature_importances_"):
        return [{"feature": name, "importance": float(value), "direction": None} for name, value in zip(feature_names, estimator.feature_importances_)]
    if hasattr(estimator, "coef_"):
        return [{"feature": name, "importance": abs(float(value)), "direction": "positive" if value >= 0 else "negative"} for name, value in zip(feature_names, estimator.coef_[0])]
    return []
