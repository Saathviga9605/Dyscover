"""Deterministic skill/domain profile builder.

Builds a per-domain skill representation from observed trial data.  All
metrics are computed directly from persisted observations; nothing is
learned or inferred beyond the arithmetic described here.
"""

from dataclasses import dataclass, field, asdict

from . import evidence
from .config import PersonalizationConfig
from .domains import domain_label, GAME_DOMAIN, GAMES_BY_DOMAIN


@dataclass
class DomainSkill:
    domain: str
    evidence_state: str
    accuracy: float | None = None
    mean_reaction_time_ms: float | None = None
    trial_count: int = 0
    valid_trial_count: int = 0
    completed_trial_count: int = 0
    incomplete_trial_count: int = 0
    correct_count: int = 0
    error_count: int = 0
    games: list[str] = field(default_factory=list)
    category: str = evidence.EvidenceState.INSUFFICIENT_DATA
    confidence: str = "low"
    reason: str | None = None
    observations: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return domain_label(self.domain)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["label"] = self.label
        return data


def _accuracy(trials) -> float | None:
    valid = [t for t in trials if evidence.is_valid(t)]
    if not valid:
        return None
    return sum(1 for t in valid if t.correctness) / len(valid)


def _timing(trials) -> float | None:
    valid = [t for t in trials if evidence.is_valid_timing(t) and t.reaction_time_ms is not None]
    if not valid:
        return None
    return sum(t.reaction_time_ms for t in valid) / len(valid)


def categorize(accuracy: float | None, config: PersonalizationConfig) -> tuple[str, str | None]:
    """Return (category, reason) from observed accuracy.

    Categories are observed-performance labels only, never clinical.
    """
    if accuracy is None:
        return evidence.EvidenceState.INSUFFICIENT_DATA, None
    if accuracy >= config.category.strength_accuracy:
        return "relative_strength", "Accuracy at or above the strength window in observed activity."
    if accuracy <= config.category.practice_accuracy:
        return "practice_opportunity", "Accuracy at or below the observation window suggests practice opportunity."
    return "developing", "Accuracy in the developing window for observed activity."


def build_domain_skill(domain: str, trials: list, config: PersonalizationConfig) -> DomainSkill:
    report = evidence.report(trials, config.evidence)
    accuracy = _accuracy(trials)
    if report["state"] == evidence.EvidenceState.SUFFICIENT_DATA:
        category, reason = categorize(accuracy, config)
    else:
        category, reason = evidence.EvidenceState.INSUFFICIENT_DATA, None
    confidence = "medium" if report["valid_trial_count"] >= 5 else "low"
    valid = [t for t in trials if evidence.is_valid(t)]
    return DomainSkill(
        domain=domain,
        evidence_state=report["state"],
        accuracy=accuracy,
        mean_reaction_time_ms=_timing(trials),
        trial_count=report["trial_count"],
        valid_trial_count=report["valid_trial_count"],
        completed_trial_count=report["completed_trial_count"],
        incomplete_trial_count=report["incomplete_trial_count"],
        correct_count=sum(1 for t in valid if t.correctness),
        error_count=len(valid) - sum(1 for t in valid if t.correctness),
        games=GAMES_BY_DOMAIN.get(domain, []),
        category=category,
        confidence=confidence,
        reason=reason,
        observations=observations_for(report["state"], accuracy, category),
    )


def observations_for(state: str, accuracy: float | None, category: str) -> list[str]:
    """Parent-safe, observation-only language (no clinical claims)."""
    if state == evidence.EvidenceState.NO_DATA:
        return ["No activity has been observed yet for this skill area."]
    if state == evidence.EvidenceState.INSUFFICIENT_DATA:
        return ["Not enough completed activity observed yet to describe this skill area."]
    accuracy_text = f"{max(0, round((accuracy or 0) * 100))}% accurate on completed observations"
    if category == "relative_strength":
        return [f"{accuracy_text}; recent activity shows a comfortable pattern."]
    if category == "practice_opportunity":
        return [f"{accuracy_text}; more practice on this skill area may help."]
    return [f"{accuracy_text}; skill area is developing."]


def build_profile(trials, config: PersonalizationConfig) -> list[DomainSkill]:
    by_domain: dict[str, list] = {}
    for trial in trials:
        domain = GAME_DOMAIN.get(trial.game_id)
        if domain is None:
            continue
        by_domain.setdefault(domain, []).append(trial)

    skills: list[DomainSkill] = []
    order = GAMES_BY_DOMAIN.keys()
    for domain in order:
        if domain in by_domain:
            skills.append(build_domain_skill(domain, by_domain[domain], config))
    return skills