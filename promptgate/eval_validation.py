from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


RISK_LEVELS = {"low", "medium", "high", "destructive"}
HANDOFF_STATUSES = {
    "auto_handoff",
    "suggested",
    "no_match",
    "skill_not_found",
    "blocked_by_risk",
    "disabled",
}
TARGET_SOURCES = {"explicit", "matched", "none"}


class EvalValidationError(ValueError):
    """Raised when an eval fixture violates the PromptGate contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise EvalValidationError(f"{path}: top-level YAML must be a mapping")
    return data


def validate_eval_file(path: Path) -> None:
    data = load_yaml(path)
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalValidationError(f"{path}: cases must be a non-empty list")

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        validate_case(path, index, case, seen_ids)


def validate_case(path: Path, index: int, case: Any, seen_ids: set[str]) -> None:
    label = f"{path}: case[{index}]"
    if not isinstance(case, dict):
        raise EvalValidationError(f"{label}: case must be a mapping")

    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise EvalValidationError(f"{label}: id must be a non-empty string")
    if case_id in seen_ids:
        raise EvalValidationError(f"{label}: duplicate id {case_id!r}")
    seen_ids.add(case_id)

    prompt = case.get("input")
    if not isinstance(prompt, str) or not prompt:
        raise EvalValidationError(f"{label}: input must be a non-empty string")

    expected = case.get("expected")
    if not isinstance(expected, dict) or not expected:
        raise EvalValidationError(f"{label}: expected must be a non-empty mapping")

    registered_skills = case.get("registered_skills", [])
    validate_registered_skills(label, registered_skills)
    validate_expected(label, expected, registered_skills)


def validate_registered_skills(label: str, registered_skills: Any) -> None:
    if not isinstance(registered_skills, list):
        raise EvalValidationError(f"{label}: registered_skills must be a list")

    seen_ids: set[str] = set()
    for skill in registered_skills:
        if not isinstance(skill, dict):
            raise EvalValidationError(f"{label}: registered skill must be a mapping")

        skill_id = skill.get("id")
        if not isinstance(skill_id, str) or not skill_id:
            raise EvalValidationError(f"{label}: registered skill id must be non-empty")
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$", skill_id):
            raise EvalValidationError(f"{label}: invalid registered skill id {skill_id!r}")
        if skill_id in seen_ids:
            raise EvalValidationError(f"{label}: duplicate registered skill {skill_id!r}")
        seen_ids.add(skill_id)

        risk_level = skill.get("risk_level")
        if risk_level not in RISK_LEVELS:
            raise EvalValidationError(f"{label}: invalid risk_level for {skill_id!r}")

        if not isinstance(skill.get("auto_invocable"), bool):
            raise EvalValidationError(f"{label}: auto_invocable must be boolean for {skill_id!r}")


def validate_expected(label: str, expected: dict[str, Any], registered_skills: list[dict[str, Any]]) -> None:
    skill_ids = {skill["id"] for skill in registered_skills}
    risk_by_skill = {skill["id"]: skill["risk_level"] for skill in registered_skills}

    if "status" in expected and expected["status"] not in HANDOFF_STATUSES:
        raise EvalValidationError(f"{label}: invalid status {expected['status']!r}")

    if "target_source" in expected and expected["target_source"] not in TARGET_SOURCES:
        raise EvalValidationError(f"{label}: invalid target_source {expected['target_source']!r}")

    target_skill = expected.get("target_skill")
    if target_skill is not None:
        if not isinstance(target_skill, str) or not target_skill:
            raise EvalValidationError(f"{label}: target_skill must be string or null")
        if target_skill not in skill_ids:
            raise EvalValidationError(f"{label}: unregistered target_skill {target_skill!r}")

    status = expected.get("status")
    if status == "auto_handoff" and target_skill is not None:
        risk_level = risk_by_skill.get(target_skill)
        if risk_level in {"high", "destructive"}:
            raise EvalValidationError(
                f"{label}: {risk_level} skill {target_skill!r} cannot use auto_handoff"
            )

    if status in {"blocked_by_risk", "skill_not_found", "no_match"}:
        if expected.get("requires_confirmation") is False:
            raise EvalValidationError(f"{label}: {status} cannot explicitly disable confirmation")

    if "clarification_needed" in expected and not isinstance(expected["clarification_needed"], bool):
        raise EvalValidationError(f"{label}: clarification_needed must be boolean")

    if "question_count" in expected:
        question_count = expected["question_count"]
        if not isinstance(question_count, int):
            raise EvalValidationError(f"{label}: question_count must be an integer")
        if expected.get("clarification_needed") is True and question_count != 1:
            raise EvalValidationError(f"{label}: question_count must be 1 when clarification is needed")

    for list_field in [
        "refined_prompt_includes",
        "exclusions",
        "output_preferences",
        "goal_includes",
        "solution_candidates",
        "should_not_assume",
        "question_includes",
    ]:
        if list_field in expected:
            value = expected[list_field]
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                raise EvalValidationError(f"{label}: {list_field} must be a list of non-empty strings")


def validate_all(evals_dir: Path) -> list[Path]:
    if not evals_dir.exists():
        raise EvalValidationError(f"{evals_dir}: evals directory does not exist")

    paths = sorted(evals_dir.glob("*.yaml"))
    if not paths:
        raise EvalValidationError(f"{evals_dir}: no eval YAML files found")

    for path in paths:
        validate_eval_file(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PromptGate eval fixtures.")
    parser.add_argument("--evals-dir", default="evals", help="Directory containing eval YAML files.")
    args = parser.parse_args()

    try:
        paths = validate_all(Path(args.evals_dir))
    except EvalValidationError as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Validated {len(paths)} eval file(s).")
    return 0
