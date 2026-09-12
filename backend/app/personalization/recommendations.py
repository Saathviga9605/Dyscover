"""Deterministic activity recommendation engine.

Produces parent-safe, observation-only activity suggestions from skill
profiles.  Recommendations:

- Are derived from observed accuracy categories (never clinical).
- Refer only to existing game activities.
- Are ordered deterministically by (priority, default game order).
- Provide a plain-language reason understandable by a parent.
- Prefer practice opportunities, then developing areas, then strengths.
- Emit a neutral suggestion when there is insufficient evidence to rank.
"""

from dataclasses import dataclass, asdict
from typing import Literal

from . import evidence
from .config import PersonalizationConfig
from .domains import DEFAULT_GAME_ORDER, domain_label

CATEGORY_PRIORITY = {
    "practice_opportunity": 30,
    "developing": 20,
    "relative_strength": 10,
}


@dataclass
class Recommendation:
    game_id: str | None
    target_domain: str | None
    priority: int
    reason: str
    category: str
    suggested_difficulty: int | None = None
    kind: Literal["game_activity", "neutral"] = "game_activity"


def build_recommendations(skills, config: PersonalizationConfig) -> list[Recommendation]:
    ranked: list[Recommendation] = []

    seen_domains: set[str] = set()
    for skill in sorted(
        [s for s in skills if s.evidence_state == evidence.EvidenceState.SUFFICIENT_DATA],
        key=lambda s: (-CATEGORY_PRIORITY.get(s.category, 0), s.domain),
    ):
        if skill.domain in seen_domains:
            continue
        seen_domains.add(skill.domain)
        game_ids = [g for g in DEFAULT_GAME_ORDER if g in skill.games]
        if not game_ids:
            continue
        game_id = game_ids[0]
        reason = _reason_for(skill.category, skill.label, config)
        ranked.append(
            Recommendation(
                game_id=game_id,
                target_domain=skill.domain,
                priority=CATEGORY_PRIORITY.get(skill.category, 0),
                reason=reason,
                category=skill.category,
                suggested_difficulty=None,
            )
        )

    if not ranked:
        ranked.append(
            Recommendation(
                game_id=None,
                target_domain=None,
                priority=0,
                reason=(
                    "Not enough completed activity has been observed yet to make activity "
                    "suggestions.  Completing a few more varied assessment activities will help."
                ),
                category=evidence.EvidenceState.INSUFFICIENT_DATA,
                kind="neutral",
            )
        )
    return ranked


def _reason_for(category: str, label: str, config: PersonalizationConfig) -> str:
    if category == "practice_opportunity":
        return f"Recent activity suggests more practice with {label.lower()} activities may be helpful."
    if category == "developing":
        return f"{label.title()} is developing; continued practice may help it grow."
    return f"Recent {label.lower()} activity looked comfortable; continuing to practise may help maintain it."


def to_dict(rec: Recommendation) -> dict:
    data = asdict(rec)
    if rec.target_domain is not None:
        data["target_domain_label"] = domain_label(rec.target_domain)
    return data