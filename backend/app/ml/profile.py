from typing import Any

LIMITATIONS = ["This is a screening-oriented observation system, not a diagnostic assessment.", "Results can be influenced by attention, fatigue, familiarity, environment, device, language background, and other factors.", "Professional evaluation may be appropriate when concerns persist."]

def build_profile(session_id: str, features: dict[str, dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
    domains: dict[str, dict[str, Any]] = {}
    observations: list[str] = []
    for name, feature in features.items():
        if feature["domain"] == "domain_performance" and feature["available"]:
            domains[name.removeprefix("domain_").removesuffix("_accuracy")] = {"status": "Observed", "accuracy": feature["value"], "source": feature["source"]}
    accuracy = features.get("overall_accuracy", {}).get("value")
    reaction = features.get("mean_reaction_time_ms", {}).get("value")
    if accuracy is not None: observations.append("Activity accuracy was recorded across completed trials.")
    if reaction is not None: observations.append("Response timing was recorded for trials with available timing data.")
    if not observations: observations.append("There is not enough completed activity data to describe observed patterns yet.")
    return {"session_id": session_id, "assessment_id": session_id, "subject_id": None, "trial_count": quality.get("trial_count", 0), "feature_schema_version": quality.get("feature_schema_version", "1.0"), "available_modalities": ["behavior"], "missing_features": [name for name, item in features.items() if not item.get("available")], "mode": "OBSERVATION_ONLY", "domains": domains, "observations": observations, "data_quality": quality, "model": {"status": "unavailable", "model_state": "unavailable", "mode": "UNAVAILABLE", "model": None, "prediction": None, "limitations": ["No validated model is available for this installation."]}, "limitations": LIMITATIONS}
