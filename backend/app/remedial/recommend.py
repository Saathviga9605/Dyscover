"""Deterministic, explainable practice-activity selection.

Selection is a pure function of (domain profile, practice history, age,
config) — no machine learning, no reinforcement learning, no unseeded
randomness.  Priority:

1. Evidence-backed practice opportunity (``practice_opportunity``).
2. Developing area with sufficient evidence (``developing``).
3. Spaced practice — prefer activities not completed within the cooldown.
4. Balanced/neutral practice when there is no focus signal.

Insufficient evidence is *never* presented as a weakness.  When there is no
focus signal the engine returns a neutral balanced activity (or
``no_activity`` when the catalog has nothing age-appropriate).
"""

from . import catalog
from .config import REMEDIAL_CONFIG
from .content import CONTENT_VERSION

_FOCUS_SCORE = {"practice_opportunity": 2, "developing": 1}

_FALLBACK_LABELS = {
    "visual-symbol-discrimination": "visual symbol",
    "orthographic-recognition": "word and letter",
    "working-memory": "memory",
    "attention-visual-search": "visual attention",
}


def _age_of(birth_year: int | None, now_year: int = 2026) -> int | None:
    if birth_year is None:
        return None
    return max(0, now_year - birth_year)


def get_child_age(profile: dict) -> int | None:
    return _age_of(profile.get("birth_year"))


def _domain_label(profile: dict, domain: str) -> str:
    for skill in profile.get("skills", []):
        if skill.get("domain") == domain:
            label = skill.get("label")
            if label:
                return label
    return _FALLBACK_LABELS.get(domain, domain)


def _skill(profile: dict, domain: str) -> dict | None:
    for skill in profile.get("skills", []):
        if skill.get("domain") == domain:
            return skill
    return None


def _recent_completions(practice_history: list) -> set[str]:
    """Activity ids completed within the cooldown window."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=REMEDIAL_CONFIG.activity_cooldown_hours)
    recent = set()
    for session in practice_history:
        if session.completed_at is not None:
            completed = session.completed_at
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            if completed >= cutoff:
                recent.add(session.activity_id)
    return recent


def select_activity(
    profile: dict,
    practice_history: list,
    age: int | None = None,
    *,
    difficulty_service=None,
    db=None,
    child_id: str | None = None,
    capabilities: tuple[str, ...] | None = None,
) -> dict:
    """Return a recommendation dict (see ``build_recommendation``).

    ``capabilities`` filters the candidate catalog.  The default
    recommendation path uses pointer-only activities so that microphone
    activities are only offered when explicitly requested.
    """
    activities = catalog.available_activities(age=age, capabilities=capabilities)
    if not activities:
        return _recommendation(None, "no_activity", None, "balanced")

    recent = _recent_completions(practice_history)

    # Focused candidates: sufficient evidence at a focus category.
    focus_candidates: list[tuple[int, catalog.ActivityDefinition]] = []
    for skill in profile.get("skills", []):
        if skill.get("evidence_state") != "sufficient_data":
            continue
        category = skill.get("category")
        if category not in _FOCUS_SCORE:
            continue
        activity = next((a for a in activities if a.target_domain == skill.get("domain")), None)
        if activity is None:
            continue
        if activity.activity_id in recent:
            continue
        focus_candidates.append((_FOCUS_SCORE[category], activity))

    focus_candidates.sort(key=lambda item: item[0], reverse=True)

    if focus_candidates:
        score, activity = focus_candidates[0]
        skill = _skill(profile, activity.target_domain)
        kind = "focused"
        reason = _focused_reason(kind, _domain_label(profile, activity.target_domain), skill.get("category"))
        return _build(activity, profile, practice_history, kind, reason, skill, difficulty_service, db, child_id, age)

    # Balanced: neutral, spaced, deterministic rotation.  Prefer activities
    # not completed within the cooldown, then least recently practiced.
    completed_counts: dict[str, int] = {}
    last_completed: dict[str, object] = {}
    for session in practice_history:
        activity_id = session.activity_id
        completed_counts[activity_id] = completed_counts.get(activity_id, 0) + 1
        if session.completed_at is not None:
            stamp = session.completed_at.replace(tzinfo=None)
            previous = last_completed.get(activity_id)
            if previous is None or stamp > previous:
                last_completed[activity_id] = stamp

    def _epoch(stamp) -> float:
        from datetime import datetime

        if stamp is None:
            return 0.0
        return (stamp - datetime(1970, 1, 1)).total_seconds()

    def _sort_key(activity: catalog.ActivityDefinition) -> tuple[int, float]:
        is_recent = 1 if activity.activity_id in recent else 0
        return (is_recent, _epoch(last_completed.get(activity.activity_id)))

    balanced = sorted(activities, key=_sort_key)
    activity = balanced[0]
    skill = _skill(profile, activity.target_domain)
    reason = f"A balanced practice activity for {_domain_label(profile, activity.target_domain)} practice."
    return _build(activity, profile, practice_history, "balanced", reason, skill, difficulty_service, db, child_id, age)


def _focused_reason(kind: str, label: str, category: str | None) -> str:
    if category == "practice_opportunity":
        return f"Recent activity suggests more practice with {label} activities may be useful."
    return f"{label.capitalize()} is still growing; a little practice may help it grow."


def _recommendation(activity, kind, skill, difficulty_result, domain_label) -> dict:
    return {
        "kind": kind,
        "activity": activity,
        "target_domain": activity["target_domain"] if activity else None,
        "target_domain_label": domain_label,
        "difficulty_level": (difficulty_result["level"] if difficulty_result else None),
        "difficulty_previous_level": (difficulty_result["previous_level"] if difficulty_result else None),
    }


def _build(activity, profile, practice_history, kind, reason, skill, difficulty_service, db, child_id, age) -> dict:
    difficulty_result = None
    if activity is not None and difficulty_service is not None and db is not None and child_id is not None:
        decision = difficulty_service(db, child_id, activity.supporting_game)
        level = max(
            REMEDIAL_CONFIG.difficulty_minimum,
            min(REMEDIAL_CONFIG.difficulty_maximum, decision.level),
        )
        difficulty_result = {"level": level, "previous_level": decision.previous_level}

    base = _recommendation(
        activity.to_dict() if activity else None,
        kind,
        skill,
        difficulty_result,
        _domain_label(profile, activity.target_domain) if activity else None,
    )
    base["reason"] = reason
    base["recommendation_version"] = REMEDIAL_CONFIG.engine_version
    base["content_version"] = CONTENT_VERSION
    return base