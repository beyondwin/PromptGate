from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldFailure:
    field: str
    expected: Any
    actual: Any
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


@dataclass(frozen=True)
class CaseScore:
    total_fields: int
    passed_fields: int
    failures: list[FieldFailure]

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def field_score(self) -> float:
        if self.total_fields == 0:
            return 1.0
        return self.passed_fields / self.total_fields

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_fields": self.total_fields,
            "passed_fields": self.passed_fields,
            "field_score": self.field_score,
            "failures": [failure.as_dict() for failure in self.failures],
        }


EXACT_FIELD_PATHS = {
    "status": ("skill_handoff", "status"),
    "target_source": ("skill_handoff", "target_source"),
    "target_skill": ("skill_handoff", "target_skill"),
    "requires_confirmation": ("safety", "requires_confirmation"),
    "clarification_needed": ("clarification", "needed"),
}


CONTAINS_FIELD_PATHS = {
    "refined_prompt_includes": ("refined_prompt",),
    "goal_includes": ("intent", "goal"),
    "solution_candidates": ("context", "solution_candidates"),
    "output_preferences": ("context", "output_preferences"),
    "question_includes": ("clarification", "question"),
}


NEGATIVE_CONTAINS_FIELDS = {"should_not_assume", "exclusions"}


def score_expected(result: dict[str, Any], expected: dict[str, Any]) -> CaseScore:
    failures: list[FieldFailure] = []
    total = 0
    passed = 0

    for field, path in EXACT_FIELD_PATHS.items():
        if field not in expected:
            continue
        total += 1
        actual = _get_path(result, path)
        if actual == expected[field]:
            passed += 1
        else:
            failures.append(_failure(field, expected[field], actual))

    if "question_count" in expected:
        total += 1
        actual = _question_count(result)
        if actual == expected["question_count"]:
            passed += 1
        else:
            failures.append(_failure("question_count", expected["question_count"], actual))

    for field, path in CONTAINS_FIELD_PATHS.items():
        if field not in expected:
            continue
        for needle in expected[field]:
            total += 1
            actual = _get_path(result, path)
            haystack = _text_for_contains(actual)
            if _contains(haystack, needle):
                passed += 1
            else:
                failures.append(_failure(field, needle, actual))

    searchable_text = _searchable_text(result)
    for field in NEGATIVE_CONTAINS_FIELDS:
        if field not in expected:
            continue
        for forbidden in expected[field]:
            total += 1
            if _contains(searchable_text, forbidden):
                failures.append(
                    FieldFailure(
                        field=field,
                        expected=f"not containing {forbidden}",
                        actual=searchable_text,
                        message=f"{field} contained forbidden text {forbidden!r}",
                    )
                )
            else:
                passed += 1

    return CaseScore(total_fields=total, passed_fields=passed, failures=failures)


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _question_count(result: dict[str, Any]) -> int:
    question = str(_get_path(result, ("clarification", "question")) or "").strip()
    return 1 if question else 0


def _text_for_contains(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _searchable_text(result: dict[str, Any]) -> str:
    chunks = [
        result.get("refined_prompt"),
        _get_path(result, ("intent", "goal")),
        _get_path(result, ("clarification", "question")),
        _get_path(result, ("clarification", "reason")),
        _get_path(result, ("skill_handoff", "reason")),
        _get_path(result, ("safety", "reason")),
        _get_path(result, ("context", "constraints")),
        _get_path(result, ("context", "exclusions")),
        _get_path(result, ("context", "output_preferences")),
        _get_path(result, ("context", "solution_candidates")),
        _get_path(result, ("context", "assumptions")),
    ]
    return "\n".join(_text_for_contains(chunk) for chunk in chunks)


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _failure(field: str, expected: Any, actual: Any) -> FieldFailure:
    return FieldFailure(
        field=field,
        expected=expected,
        actual=actual,
        message=f"expected {field}={expected!r}, got {actual!r}",
    )
