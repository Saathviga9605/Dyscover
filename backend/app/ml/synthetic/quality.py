"""Dataset quality scenarios, semantic validation, and negative testing fixtures.

Provides generators for edge-case quality conditions and deliberately invalid fixtures
used to verify dataset validation and corruption handling.
"""

from __future__ import annotations

import copy
from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME


def validate_synthetic_row(row: dict[str, Any]) -> list[str]:
    """Validate a synthetic session row against the canonical feature registry and provenance rules.

    Returns a list of issue strings. An empty list signifies a fully valid record.
    """
    issues: list[str] = []

    # Check synthetic provenance
    if not row.get("synthetic"):
        issues.append("missing_synthetic_flag")
    if not row.get("simulator_version"):
        issues.append("missing_simulator_version")
    if not row.get("subject_id"):
        issues.append("missing_subject_id")
    if not row.get("session_id"):
        issues.append("missing_session_id")
    if not row.get("target"):
        issues.append("missing_target")

    features = row.get("features", {})
    if not isinstance(features, dict) or not features:
        issues.append("missing_or_empty_features")
        return issues

    for name, item in features.items():
        definition = REGISTRY_BY_NAME.get(name)
        if definition is None:
            issues.append(f"unknown_feature:{name}")
            continue

        if not isinstance(item, dict):
            issues.append(f"malformed_feature_record:{name}")
            continue

        val = item.get("value")
        is_avail = bool(item.get("available"))

        # Availability consistency: if available is True, value must not be None
        if is_avail != (val is not None):
            issues.append(f"availability_mismatch:{name}")

        if val is not None:
            # Type check
            if not isinstance(val, (int, float)):
                issues.append(f"invalid_datatype:{name}")
                continue

            # Bound checks
            if definition.minimum is not None and val < definition.minimum:
                issues.append(f"below_minimum:{name}:{val}<{definition.minimum}")
            if definition.maximum is not None and val > definition.maximum:
                issues.append(f"above_maximum:{name}:{val}>{definition.maximum}")

    return issues


def generate_negative_fixtures(valid_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Produce deliberately corrupted fixtures from a valid row to test validation gates.

    Each returned fixture is tagged with `is_negative_test_fixture: True` and an expected issue.
    """
    fixtures: dict[str, dict[str, Any]] = {}

    # 1. Missing synthetic flag
    f_missing_flag = copy.deepcopy(valid_row)
    f_missing_flag["synthetic"] = False
    f_missing_flag["is_negative_test_fixture"] = True
    f_missing_flag["expected_issue"] = "missing_synthetic_flag"
    fixtures["missing_synthetic_flag"] = f_missing_flag

    # 2. Unknown feature name
    f_unknown_feat = copy.deepcopy(valid_row)
    f_unknown_feat["features"]["unregistered_invented_feature"] = {
        "name": "unregistered_invented_feature",
        "value": 42.0,
        "available": True,
    }
    f_unknown_feat["is_negative_test_fixture"] = True
    f_unknown_feat["expected_issue"] = "unknown_feature:unregistered_invented_feature"
    fixtures["unknown_feature"] = f_unknown_feat

    # 3. Accuracy below minimum (< 0.0)
    f_below_min = copy.deepcopy(valid_row)
    if "overall_accuracy" in f_below_min["features"]:
        f_below_min["features"]["overall_accuracy"]["value"] = -0.25
        f_below_min["features"]["overall_accuracy"]["available"] = True
    f_below_min["is_negative_test_fixture"] = True
    f_below_min["expected_issue"] = "below_minimum:overall_accuracy"
    fixtures["below_minimum"] = f_below_min

    # 4. Accuracy above maximum (> 1.0)
    f_above_max = copy.deepcopy(valid_row)
    if "overall_accuracy" in f_above_max["features"]:
        f_above_max["features"]["overall_accuracy"]["value"] = 1.45
        f_above_max["features"]["overall_accuracy"]["available"] = True
    f_above_max["is_negative_test_fixture"] = True
    f_above_max["expected_issue"] = "above_maximum:overall_accuracy"
    fixtures["above_maximum"] = f_above_max

    # 5. Invalid datatype (string instead of numeric)
    f_bad_type = copy.deepcopy(valid_row)
    if "mean_reaction_time_ms" in f_bad_type["features"]:
        f_bad_type["features"]["mean_reaction_time_ms"]["value"] = "FAST"
        f_bad_type["features"]["mean_reaction_time_ms"]["available"] = True
    f_bad_type["is_negative_test_fixture"] = True
    f_bad_type["expected_issue"] = "invalid_datatype:mean_reaction_time_ms"
    fixtures["invalid_datatype"] = f_bad_type

    # 6. Availability mismatch (available True but value None)
    f_avail_mismatch = copy.deepcopy(valid_row)
    if "gaze_mean_fixation_duration_ms" in f_avail_mismatch["features"]:
        f_avail_mismatch["features"]["gaze_mean_fixation_duration_ms"]["value"] = None
        f_avail_mismatch["features"]["gaze_mean_fixation_duration_ms"]["available"] = True
    f_avail_mismatch["is_negative_test_fixture"] = True
    f_avail_mismatch["expected_issue"] = "availability_mismatch:gaze_mean_fixation_duration_ms"
    fixtures["availability_mismatch"] = f_avail_mismatch

    return fixtures

