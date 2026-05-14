from __future__ import annotations

import copy
import re
from typing import Any

from .config import PromptGateConfig
from .registry import SkillRegistry


EXPLICIT_SKILL_PATTERN = re.compile(r"(?:^|\s)[$@/]([a-zA-Z0-9][a-zA-Z0-9._:-]*)")
HIGH_RISK_LEVELS = {"high", "destructive"}


def extract_explicit_skill_mention(raw_prompt: str) -> str | None:
    match = EXPLICIT_SKILL_PATTERN.search(raw_prompt)
    return match.group(1) if match else None


def apply_guards(
    draft: dict[str, Any],
    raw_prompt: str,
    config: PromptGateConfig,
    registry: SkillRegistry,
) -> dict[str, Any]:
    result = copy.deepcopy(draft)
    result["original_prompt"] = raw_prompt
    result["refined_prompt"] = result.get("refined_prompt") or raw_prompt
    if not result["refined_prompt"].strip():
        result["refined_prompt"] = raw_prompt

    _clamp_confidences(result)
    _guard_clarification(result)

    handoff = result["skill_handoff"]
    handoff["mode"] = config.mode

    if config.mode == "off":
        _disable_handoff(result, "Handoff mode is off.")
        return result

    explicit = extract_explicit_skill_mention(raw_prompt)
    if explicit is not None:
        handoff["explicit_skill_mention"] = explicit
        if not registry.has(explicit):
            _clear_handoff(result, status="skill_not_found", reason="Explicitly mentioned skill is not registered.")
            return result
        handoff["target_skill"] = explicit
        handoff["target_source"] = "explicit"
        handoff["confidence"] = 1

    target_skill = handoff.get("target_skill")
    if target_skill is not None and not registry.has(target_skill):
        status = "skill_not_found" if explicit else "no_match"
        reason = "Target skill is not registered."
        _clear_handoff(result, status=status, reason=reason)
        return result

    _guard_target_source_consistency(result, registry)

    target_skill = result["skill_handoff"].get("target_skill")
    if target_skill is None:
        result["skill_handoff"]["status"] = _status_without_target(result["skill_handoff"].get("status"))
        result["skill_handoff"]["target_source"] = "none"
        result["skill_handoff"]["confidence"] = 0
        return result

    skill = registry.get(target_skill)
    result["safety"]["risk_level"] = skill.risk_level

    if skill.risk_level in HIGH_RISK_LEVELS:
        result["skill_handoff"]["status"] = "blocked_by_risk"
        result["safety"]["requires_confirmation"] = True
        result["safety"]["reason"] = f"{skill.risk_level} skill cannot be auto-invoked."
        return result

    result["safety"]["requires_confirmation"] = False

    if config.mode == "suggest":
        result["skill_handoff"]["status"] = "suggested"
        return result

    if not skill.auto_invocable:
        result["skill_handoff"]["status"] = "suggested"
        result["skill_handoff"]["reason"] = "Matched skill is not auto-invocable."
        return result

    confidence = float(result["skill_handoff"].get("confidence", 0))
    if confidence >= config.auto_handoff_threshold:
        result["skill_handoff"]["status"] = "auto_handoff"
    else:
        result["skill_handoff"]["status"] = "suggested"
        result["skill_handoff"]["reason"] = "Matched skill did not meet auto handoff threshold."

    return result


def _clamp_confidences(result: dict[str, Any]) -> None:
    result["intent"]["confidence"] = _clamp(float(result["intent"].get("confidence", 0)))
    result["skill_handoff"]["confidence"] = _clamp(float(result["skill_handoff"].get("confidence", 0)))


def _clamp(value: float) -> float:
    return max(0, min(1, value))


def _guard_clarification(result: dict[str, Any]) -> None:
    clarification = result["clarification"]
    if clarification.get("needed") is True and not str(clarification.get("question") or "").strip():
        clarification["question"] = "어떤 결과물을 원하시는지 한 가지만 알려주세요."
        clarification["reason"] = clarification.get("reason") or "Clarification is required but no usable question was provided."


def _guard_target_source_consistency(result: dict[str, Any], registry: SkillRegistry) -> None:
    handoff = result["skill_handoff"]
    target_source = handoff.get("target_source")
    target_skill = handoff.get("target_skill")
    explicit = handoff.get("explicit_skill_mention")

    if target_source == "none":
        handoff["target_skill"] = None
        return

    if target_source == "explicit":
        if not explicit or target_skill != explicit:
            _clear_handoff(result, status="no_match", reason="Explicit handoff fields were inconsistent.")
        return

    if target_source == "matched":
        if target_skill is None or not registry.has(target_skill):
            _clear_handoff(result, status="no_match", reason="Matched handoff did not reference a registered skill.")
        return

    _clear_handoff(result, status="no_match", reason="Unknown target_source.")


def _status_without_target(status: str | None) -> str:
    if status in {"skill_not_found", "disabled"}:
        return status
    return "no_match"


def _clear_handoff(result: dict[str, Any], status: str, reason: str) -> None:
    result["skill_handoff"]["target_skill"] = None
    result["skill_handoff"]["target_source"] = "none"
    result["skill_handoff"]["confidence"] = 0
    result["skill_handoff"]["status"] = status
    result["skill_handoff"]["reason"] = reason


def _disable_handoff(result: dict[str, Any], reason: str) -> None:
    _clear_handoff(result, status="disabled", reason=reason)
