from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time as a naive UTC datetime (the storage convention for all models)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
