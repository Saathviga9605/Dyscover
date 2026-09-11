import re
from collections import Counter

from .schemas import AlignmentItem, ReadingAlignment, ReadingErrorType


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower(), flags=re.UNICODE)


def align_reading(expected_text: str, transcript_text: str) -> ReadingAlignment:
    expected = tokenize(expected_text)
    actual = tokenize(transcript_text)
    if not expected:
        return ReadingAlignment(expected_text=expected_text, transcript_text=transcript_text, items=[], matched_words=0, substitutions=0, omissions=0, insertions=len(actual), repetitions=0, order_differences=0, quality="UNAVAILABLE")
    items: list[AlignmentItem] = []
    substitutions = omissions = insertions = 0
    for index in range(max(len(expected), len(actual))):
        expected_word = expected[index] if index < len(expected) else None
        actual_word = actual[index] if index < len(actual) else None
        if expected_word == actual_word and expected_word is not None:
            items.append(AlignmentItem(expected=expected_word, actual=actual_word, error_type=ReadingErrorType.CORRECT))
        elif expected_word is None:
            insertions += 1
            items.append(AlignmentItem(actual=actual_word, error_type=ReadingErrorType.INSERTION))
        elif actual_word is None:
            omissions += 1
            items.append(AlignmentItem(expected=expected_word, error_type=ReadingErrorType.OMISSION))
        else:
            substitutions += 1
            items.append(AlignmentItem(expected=expected_word, actual=actual_word, error_type=ReadingErrorType.SUBSTITUTION))
    repeats = sum(count - 1 for count in Counter(actual).values() if count > 1)
    order_differences = int(len(expected) == len(actual) and expected != actual and Counter(expected) == Counter(actual))
    if repeats:
        for item in items:
            if item.actual and actual.count(item.actual) > 1 and item.error_type is ReadingErrorType.CORRECT:
                item.error_type = ReadingErrorType.REPETITION
    return ReadingAlignment(expected_text=expected_text, transcript_text=transcript_text, items=items, matched_words=sum(item.error_type is ReadingErrorType.CORRECT for item in items), substitutions=substitutions, omissions=omissions, insertions=insertions, repetitions=repeats, order_differences=order_differences)
