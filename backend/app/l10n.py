"""Canonical language and content-availability configuration (Stage 7).

Single source of truth for which languages is supported, which locale each
language maps to, and which activities carry genuinely available content in
a given language.  English is the fallback language and the only language for
which all existing content is curated.

Availability is *honest*: an activity is listed for a language only when its
stimulus content is actually usable in that language.  No activity is
silently "translated"; unavailable activities are surfaced as unavailable.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"

# Content/asset edition for language-aware stimulus families.  Bumped when
# curated language content changes so persisted records stay interpretable.
L10N_CONTENT_VERSION = "1.0"

LANGUAGES: dict[str, dict[str, object]] = {
    "en": {
        "code": "en",
        "name": "English",
        "native_name": "English",
        "locale": "en-US",
        "default": True,
    },
    "ta": {
        "code": "ta",
        "name": "Tamil",
        "native_name": "தமிழ்",
        "locale": "ta-IN",
        "default": False,
    },
}

SUPPORTED_LANGUAGE_CODES: frozenset[str] = frozenset(LANGUAGES)

# Assessment activities (five visual games + three speech games).
_ASSESSMENT_ACTIVITIES: dict[str, frozenset[str]] = {
    # Latin-letter discrimination -> script-specific.
    "letter-detective": frozenset({"en"}),
    # Orientation discrimination; stimulus glyphs are incidental shapes and
    # scoring depends only on orientation, so the task is language-neutral.
    "mirror-match": frozenset({"en", "ta"}),
    # English orthographic word content.
    "word-flash": frozenset({"en"}),
    # Options are English word labels.
    "sequence-quest": frozenset({"en"}),
    # English word-search grid.
    "word-maze": frozenset({"en"}),
    # Speech content is curated in English only.
    "sound-quest-adventure": frozenset({"en"}),
    "letter-bubble-pop": frozenset({"en"}),
    "maze-runner-rush": frozenset({"en"}),
}

# Remedial practice activities (supporting symbols/letters/words).
_PRACTICE_ACTIVITIES: dict[str, frozenset[str]] = {
    # Shape/symbol matching pools -> language-neutral.
    "symbol-match": frozenset({"en", "ta"}),
    # Latin letters + English words.
    "word-builder": frozenset({"en"}),
    # English item labels.
    "sequence-recall": frozenset({"en"}),
    # English word targets.
    "visual-search": frozenset({"en"}),
    # English speech content.
    "sound-quest": frozenset({"en"}),
    "letter-pop": frozenset({"en"}),
    "maze-ran": frozenset({"en"}),
}

ACTIVITY_LANGUAGES: dict[str, frozenset[str]] = {
    **_ASSESSMENT_ACTIVITIES,
    **_PRACTICE_ACTIVITIES,
}


def is_supported(language: str | None) -> bool:
    return language in SUPPORTED_LANGUAGE_CODES


def resolve_language(language: str | None) -> str:
    """Resolve to a supported language, falling back to English."""
    if language in SUPPORTED_LANGUAGE_CODES:
        return language
    return DEFAULT_LANGUAGE


def locale_for(language: str | None) -> str:
    resolved = resolve_language(language)
    return str(LANGUAGES[resolved]["locale"])


def language_name(language: str | None) -> str:
    resolved = resolve_language(language)
    return str(LANGUAGES[resolved]["name"])


def language_native_name(language: str | None) -> str:
    resolved = resolve_language(language)
    return str(LANGUAGES[resolved]["native_name"])


def activities_for(language: str | None) -> frozenset[str]:
    """All activity ids with genuinely available content in *language*."""
    resolved = resolve_language(language)
    return frozenset(
        activity_id
        for activity_id, languages in ACTIVITY_LANGUAGES.items()
        if resolved in languages
    )


def is_activity_available(activity_id: str, language: str | None) -> bool:
    languages = ACTIVITY_LANGUAGES.get(activity_id, frozenset())
    return resolve_language(language) in languages


def languages_for_activity(activity_id: str) -> frozenset[str]:
    return ACTIVITY_LANGUAGES.get(activity_id, frozenset())