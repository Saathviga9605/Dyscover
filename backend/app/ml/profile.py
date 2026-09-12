from typing import Any

LIMITATIONS = ["This is a screening-oriented observation system, not a diagnostic assessment.", "Results can be influenced by attention, fatigue, familiarity, environment, device, language background, and other factors.", "Professional evaluation may be appropriate when concerns persist."]

_MODALITY_OBSERVATIONS = {
    "gaze": ["Eye-movement observations were recorded in activities where eye tracking was enabled."],
    "speech": ["Speech observations were recorded in activities where voice input was enabled."],
    "text": ["Recognized-speech words were retained as text features while audio itself was not stored."],
}

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

    available_modalities = sorted(_available_modalities(features))
    for modality in available_modalities:
        observations.extend(_MODALITY_OBSERVATIONS.get(modality, []))
    speech_available = features.get("speech_available", {}).get("value") == 0
    if speech_available:
        observations.append("Voice input was offered, but no recognized speech was captured.")

    if not observations: observations.append("There is not enough completed activity data to describe observed patterns yet.")
    return {"session_id": session_id, "assessment_id": session_id, "subject_id": None, "trial_count": quality.get("trial_count", 0), "feature_schema_version": quality.get("feature_schema_version", "1.0"), "available_modalities": available_modalities, "missing_features": [name for name, item in features.items() if not item.get("available")], "mode": "OBSERVATION_ONLY", "domains": domains, "observations": observations, "data_quality": quality, "model": {"status": "unavailable", "model_state": "unavailable", "mode": "UNAVAILABLE", "model": None, "prediction": None, "limitations": ["No validated model is available for this installation."]}, "limitations": LIMITATIONS}


def _available_modalities(features: dict[str, dict[str, Any]]) -> set[str]:
    by_modality: dict[str, list[bool]] = {}
    for item in features.values():
        by_modality.setdefault(item.get("modality", "behavior"), []).append(bool(item.get("available")))
    explicit = {"behavior", "gaze", "speech", "text"}
    available: set[str] = set()
    for modality, flags in by_modality.items():
        if modality not in explicit:
            continue
        if any(flags):
            available.add(modality)
    if not available:
        available = {"behavior"}
    return available