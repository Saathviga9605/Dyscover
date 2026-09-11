from collections import Counter
from app.ml.feature_registry import REGISTRY_BY_NAME
from .alignment import tokenize


def extract_text_features(text: str, language: str = "en") -> dict[str, dict[str, object]]:
    tokens = tokenize(text)
    counts = Counter(tokens)
    unique = len(counts)
    total = len(tokens)
    return {
        "text_token_count": {"name": "text_token_count", "value": total, "unit": "count", "source": "transcript", "domain": "lexical", "available": bool(text), "status": "available" if text else "missing", "modality": "text", "language": language, "feature_version": "1.0", "provider": "deterministic"},
        "text_unique_token_count": {"name": "text_unique_token_count", "value": unique if text else None, "unit": "count", "source": "transcript", "domain": "lexical", "available": bool(text), "status": "available" if text else "missing", "modality": "text", "language": language, "feature_version": "1.0", "provider": "deterministic"},
        "text_type_token_ratio": {"name": "text_type_token_ratio", "value": unique / total if total else None, "unit": "proportion", "source": "transcript", "domain": "lexical", "available": bool(tokens), "status": "available" if tokens else "missing", "modality": "text", "language": language, "feature_version": "1.0", "provider": "deterministic"},
        "text_repetition_count": {"name": "text_repetition_count", "value": sum(count - 1 for count in counts.values() if count > 1) if text else None, "unit": "count", "source": "transcript", "domain": "lexical", "available": bool(text), "status": "available" if text else "missing", "modality": "text", "language": language, "feature_version": "1.0", "provider": "deterministic"},
    }
