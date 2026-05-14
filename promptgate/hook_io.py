from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Any, Callable, Mapping, TextIO

from .llm import PromptGateProvider
from .preflight import PreflightDecision, analyze_preflight
from .runtime import run_promptgate


Runner = Callable[..., dict[str, Any]]


def extract_prompt(payload: Mapping[str, object]) -> str:
    for key in ("prompt", "message", "userPrompt"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def format_additional_context(
    result: Mapping[str, object],
    preflight: PreflightDecision | None = None,
    runtime_error: str | None = None,
) -> str:
    if runtime_error is not None:
        original = str(result.get("original_prompt", ""))
        return (
            "PromptGate runtime unavailable.\n"
            "Use the user's prompt as raw input. Do not invent a skill handoff.\n"
            f"Original prompt: {original}\n"
            f"Reason: {runtime_error}"
        )

    intent = _mapping(result.get("intent"))
    handoff = _mapping(result.get("skill_handoff"))
    safety = _mapping(result.get("safety"))
    context_lines = [
        "PromptGate runtime result:",
        f"- Original prompt: {result.get('original_prompt', '')}",
        f"- Refined prompt: {result.get('refined_prompt', '')}",
        f"- Intent: {intent.get('domain', 'general')} / {intent.get('task_type', 'respond')}",
        f"- Handoff: {handoff.get('status', 'no_match')}",
        (
            "- Safety: "
            f"{safety.get('risk_level', 'low')}, "
            f"confirmation required: {str(safety.get('requires_confirmation', False)).lower()}"
        ),
    ]
    if preflight is not None:
        context_lines.append(
            f"- Preflight: {preflight.recommended_next}, clarity {preflight.clarity_score}"
        )
    context_lines.append("")
    context_lines.append(
        "Use the refined prompt as the downstream request. Preserve exclusions and do not treat solution candidates as requirements."
    )
    return "\n".join(context_lines)


def format_bypass_context(raw_prompt: str) -> str:
    return (
        "PromptGate bypass active.\n"
        "Use the user's prompt as raw input without normalization or skill handoff.\n"
        f"Original prompt: {raw_prompt}"
    )


def build_hook_output(additional_context: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }


def run_user_prompt_submit_hook(
    stdin: TextIO,
    stdout: TextIO,
    project_root: Path | None = None,
    provider: PromptGateProvider | None = None,
    runner: Runner | None = None,
) -> int:
    try:
        payload = json.load(stdin)
    except json.JSONDecodeError as exc:
        context = format_additional_context(
            {"original_prompt": ""},
            runtime_error=f"Invalid hook JSON input: {exc}",
        )
        _write_output(stdout, context)
        return 0

    if not isinstance(payload, dict):
        context = format_additional_context(
            {"original_prompt": ""},
            runtime_error="Hook input must be a JSON object.",
        )
        _write_output(stdout, context)
        return 0

    raw_prompt = extract_prompt(payload)
    preflight = analyze_preflight(raw_prompt)
    if preflight.bypass:
        _write_output(stdout, format_bypass_context(raw_prompt))
        return 0

    active_runner = runner or run_promptgate
    try:
        result = active_runner(raw_prompt, provider=provider, project_root=project_root)
        context = format_additional_context(result, preflight=preflight)
    except Exception as exc:
        context = format_additional_context(
            {"original_prompt": raw_prompt},
            runtime_error=str(exc),
        )
    _write_output(stdout, context)
    return 0


def main() -> int:
    return run_user_prompt_submit_hook(sys.stdin, sys.stdout)


def _write_output(stdout: TextIO, additional_context: str) -> None:
    stdout.write(json.dumps(build_hook_output(additional_context), ensure_ascii=False))
    stdout.write("\n")


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}
