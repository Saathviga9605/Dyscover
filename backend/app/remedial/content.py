"""Minimal versioned stimulus/content abstraction (Stage 6).

Stimuli are generated deterministically at practice time from versioned,
curated content families.  This module owns the *families and their
versions* so that content can be curated independently of the engine.

The families below are plain, child-friendly material (letters, shapes,
short words, sequence items).  They are content, not clinical material.
"""

from .config import REMEDIAL_CONFIG

CONTENT_VERSION = REMEDIAL_CONFIG.content_version

# Curated, deterministic content pools per activity.  Each pool is a tuple so
# iteration order is stable and reproducible.
CONTENT: dict[str, dict[str, object]] = {
    "symbol-match": {
        "symbols": (
            "\u25b3", "\u25b4", "\u25b5", "\u25bd",
            "\u25cf", "\u25c9", "\u25a0", "\u25a1",
            "\u25c6", "\u25c7", "\u2605", "\u2606",
            "\u2190", "\u2192", "\u2191", "\u2193",
        ),
        "targets_per_trial": 1,
    },
    "word-builder": {
        "letters": tuple("abcdefghijklmnopqrstuvwxyz"),
        "words": (
            "cat", "dog", "sun", "hat", "run",
            "bed", "fox", "cup", "map", "net",
        ),
    },
    "sequence-recall": {
        "items": (
            "star", "ball", "fish", "bell", "cap",
            "tree", "boat", "cake", "duck", "kite",
        ),
    },
    "visual-search": {
        "targets": (
            "star", "ball", "fish", "bell", "cap",
            "tree", "boat", "cake", "duck", "kite",
        ),
        "distractors": ("ball", "fish", "bell", "cap", "tree", "boat"),
    },
    "sound-quest": {
        "words": (
            "cat", "dog", "sun", "hat", "run",
            "bed", "fox", "cup", "map", "net",
        ),
    },
    "letter-pop": {
        "letters": tuple("abcdefghiklmoprstuvw"),
    },
    "maze-ran": {
        "words": (
            "the", "and", "cat", "dog", "one",
            "two", "red", "big", "go", "of",
        ),
    },
}


def speech_tasks(activity_id: str, count: int = 5, seed: int = 0) -> list[dict]:
    """Deterministic reading-aloud tasks derived from curated word pools.

    Produces ``ReadingTask``-shaped dicts used by the speech practice
    adapter.  Selection is reproducible for a given ``seed``.
    """
    from app.speech.schemas import ReadingTask

    from .catalog import get_activity

    activity = get_activity(activity_id)
    if activity is None or activity.activity_type != "speech":
        return []
    family = "letters" if activity_id == "letter-pop" else "words"
    pool = CONTENT.get(activity_id, {}).get(family, ())
    if not isinstance(pool, tuple) or not pool:
        return []
    tasks: list[ReadingTask] = []
    for index in range(count):
        position = (index + seed) % len(pool)
        word = pool[position]
        tasks.append(
            ReadingTask(
                task_id=f"{activity_id}-{index + 1}-{word}",
                expected_text=word,
                language="en",
                difficulty=max(1, min(5, len(word))),
                content_type="word",
                version=str(CONTENT_VERSION),
            )
        )
    return [task.model_dump() for task in tasks]


def content_summary() -> dict:
    """Stable, parent-safe summary of the curated content pools."""
    labels = {
        "symbol-match": "shapes and symbols",
        "word-builder": "letters and short words",
        "sequence-recall": "picture sequences",
        "visual-search": "finding a target picture",
        "sound-quest": "short words to read aloud",
        "letter-pop": "letters to name aloud",
        "maze-ran": "short words to say quickly",
    }
    return {
        "version": CONTENT_VERSION,
        "activities": [
            {
                "activity_id": activity_id,
                "family": labels.get(activity_id, activity_id),
                "pool_sizes": {k: len(v) for k, v in pools.items() if isinstance(v, tuple)},
            }
            for activity_id, pools in CONTENT.items()
        ],
    }


def pool(activity_id: str, family: str) -> tuple[str, ...]:
    """Return a curated pool, or an empty tuple for unknown content."""
    entry = CONTENT.get(activity_id, {})
    value = entry.get(family)
    return value if isinstance(value, tuple) else ()