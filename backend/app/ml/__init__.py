"""Research-safe feature engineering and baseline ML infrastructure."""

FEATURE_SCHEMA_VERSION = "1.0"
FEATURE_EXTRACTOR_VERSION = "1.0"

# Speech ML submodule is lazily loaded to avoid heavy dependencies at startup
# Use: from app.ml.speech import ...

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "FEATURE_EXTRACTOR_VERSION",
]
