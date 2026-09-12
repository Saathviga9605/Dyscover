"""Remedial learning engine.

Stage 6 provides educational practice activities for children.  It is an
educational-support subsystem built around the Stage 5 personalization
domain profile:

    OBSERVE -> DOMAIN PROFILE -> PERSONALIZE -> RECOMMEND PRACTICE
    -> CHILD PRACTICES -> COLLECT ACTIVITY TELEMETRY
    -> UPDATE OBSERVATIONS -> ADAPT FUTURE PRACTICE

Everything in this package is explicitly *educational support*.  It does not
diagnose, treat, or clinically evaluate dyslexia.  Practice data is stored
separately from assessment evidence and never feeds the assessment pipeline.
"""

REMEDIAL_ENGINE_VERSION = "1.0.0"
REMEDIAL_CONTENT_VERSION = "1.0"
REMEDIAL_MODE = "practice"
# Canonical event contract schema version shared with interaction events.
REMEDIAL_EVENT_SCHEMA_VERSION = "2.0"

__all__ = [
    "REMEDIAL_ENGINE_VERSION",
    "REMEDIAL_CONTENT_VERSION",
    "REMEDIAL_MODE",
    "REMEDIAL_EVENT_SCHEMA_VERSION",
]