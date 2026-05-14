from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_evals import validate_all

from .llm import FakeProvider
from .runtime import run_promptgate


VALID_DRAFT = {
    "original_prompt": "정리좀",
    "refined_prompt": "문장을 자연스럽게 정리해줘.",
    "intent": {
        "goal": "문장을 자연스럽게 정리한다.",
        "domain": "writing",
        "task_type": "rewrite",
        "confidence": 0.9,
    },
    "context": {
        "background": [],
        "constraints": [],
        "exclusions": [],
        "output_preferences": ["natural"],
        "solution_candidates": [],
        "assumptions": [],
    },
    "clarification": {
        "needed": False,
        "question": None,
        "reason": None,
    },
    "skill_handoff": {
        "mode": "auto",
        "explicit_skill_mention": None,
        "target_skill": None,
        "target_source": "none",
        "confidence": 0,
        "status": "no_match",
        "reason": None,
    },
    "safety": {
        "risk_level": "low",
        "requires_confirmation": False,
        "reason": None,
    },
}


def run_eval_suite(project_root: Path | None = None) -> str:
    root = project_root or Path.cwd()
    eval_paths = validate_all(root / "evals")
    _run_guard_smoke(root)
    return (
        f"Validated {len(eval_paths)} eval file(s).\n"
        "Deterministic runtime guard checks passed."
    )


def _run_guard_smoke(project_root: Path) -> None:
    draft = copy.deepcopy(VALID_DRAFT)
    draft["skill_handoff"]["target_skill"] = "invented-skill"
    draft["skill_handoff"]["target_source"] = "matched"
    draft["skill_handoff"]["status"] = "auto_handoff"
    provider = FakeProvider([json.dumps(draft, ensure_ascii=False)])
    result = run_promptgate("정리해줘", provider=provider, project_root=project_root)
    if result["skill_handoff"]["status"] != "no_match":
        raise AssertionError("invented skill was not cleared by runtime guards")
