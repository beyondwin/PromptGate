from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .resources import runtime_root

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised in dependency-light environments.
    Draft202012Validator = None


class ResultValidationError(ValueError):
    """Raised when a PromptGateResult violates the canonical schema."""


def load_result_schema(project_root: Path | None = None) -> dict[str, Any]:
    root = runtime_root(project_root)
    schema_path = root / "core/output-contract/promptgate-result.schema.json"
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_json_document(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ResultValidationError("PromptGateResult JSON must be an object")
    return parsed


def validate_result(result: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    active_schema = schema or load_result_schema()
    if Draft202012Validator is None:
        _validate_schema_subset(result, active_schema)
        return

    validator = Draft202012Validator(active_schema)
    errors = sorted(validator.iter_errors(result), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path) or "<root>"
        raise ResultValidationError(f"{path}: {first.message}")


def build_fallback_result(raw_prompt: str, mode: str, reason: str) -> dict[str, Any]:
    return {
        "original_prompt": raw_prompt,
        "refined_prompt": raw_prompt,
        "intent": {
            "goal": "Process the user's request as written.",
            "domain": "general",
            "task_type": "respond",
            "confidence": 0.2,
        },
        "context": {
            "background": [],
            "constraints": [],
            "exclusions": [],
            "output_preferences": [],
            "solution_candidates": [],
            "assumptions": [],
        },
        "clarification": {
            "needed": False,
            "question": None,
            "reason": "PromptGate used fallback because the LLM result was invalid.",
        },
        "skill_handoff": {
            "mode": mode,
            "explicit_skill_mention": None,
            "target_skill": None,
            "target_source": "none",
            "confidence": 0,
            "status": "no_match",
            "reason": reason,
        },
        "safety": {
            "risk_level": "low",
            "requires_confirmation": False,
            "reason": None,
        },
    }


def provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    cleaned = copy.deepcopy(schema)
    _remove_keys_recursive(
        cleaned,
        {
            "$schema",
            "$id",
            "title",
            "minLength",
            "minimum",
            "maximum",
            "description",
        },
    )
    _normalize_nullable_types(cleaned)
    return cleaned


def _remove_keys_recursive(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        for key in list(value.keys()):
            if key in keys:
                value.pop(key)
            else:
                _remove_keys_recursive(value[key], keys)
    elif isinstance(value, list):
        for item in value:
            _remove_keys_recursive(item, keys)


def _normalize_nullable_types(value: Any) -> None:
    if isinstance(value, dict):
        type_value = value.get("type")
        if isinstance(type_value, list):
            value.pop("type")
            value["anyOf"] = [{"type": item} for item in type_value]
        for child in value.values():
            _normalize_nullable_types(child)
    elif isinstance(value, list):
        for item in value:
            _normalize_nullable_types(item)


def _validate_schema_subset(value: Any, schema: dict[str, Any], path: str = "<root>") -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise ResultValidationError(f"{path}: value {value!r} is not in enum")

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        raise ResultValidationError(f"{path}: expected type {expected_type!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                raise ResultValidationError(f"{path}: missing required field {field!r}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise ResultValidationError(f"{path}: additional properties {sorted(extra)!r} are not allowed")

        for key, child_schema in properties.items():
            if key in value:
                _validate_schema_subset(value[key], child_schema, f"{path}.{key}" if path != "<root>" else key)

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema_subset(item, schema["items"], f"{path}[{index}]")

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        raise ResultValidationError(f"{path}: string is shorter than minLength")

    if isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            raise ResultValidationError(f"{path}: number is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ResultValidationError(f"{path}: number is above maximum")


def _matches_type(value: Any, expected_type: str | list[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True
