from __future__ import annotations

import json
from typing import Any

from .config import PromptGateConfig
from .llm import PromptGateRequest
from .registry import SkillRegistry
from .result import provider_schema


SYSTEM_PROMPT = """You are PromptGate, a prompt refinement engine and external skill handoff layer.

Return JSON only.
The returned object must be a PromptGateResult.
Do not execute downstream work.
Do not invent skill names.
Treat registered skills as a closed-world list.
Treat solution ideas from the user as candidates, not confirmed requirements.
Preserve exclusions such as no code, direction only, and do not implement.
Ask one clarifying question only when missing information materially changes the downstream task.
"""


def build_promptgate_request(
    raw_prompt: str,
    config: PromptGateConfig,
    registry: SkillRegistry,
    schema: dict[str, Any],
) -> PromptGateRequest:
    response_schema = provider_schema(schema)
    user_payload = {
        "raw_prompt": raw_prompt,
        "mode": config.mode,
        "auto_handoff_threshold": config.auto_handoff_threshold,
        "risk_policy": config.risk_policy,
        "registered_skills_closed_world": registry.as_prompt_payload(),
        "required_behavior": [
            "Produce a PromptGateResult object.",
            "Treat registered skills as closed-world data.",
            "Use only registered skill ids from registered_skills_closed_world.",
            "Set target_skill to null when no registered skill matches.",
            "Do not auto hand off high-risk or destructive skills.",
            "Make refined_prompt directly usable by a downstream agent or skill.",
        ],
    }

    return PromptGateRequest(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2),
        response_schema=response_schema,
        raw_prompt=raw_prompt,
    )
