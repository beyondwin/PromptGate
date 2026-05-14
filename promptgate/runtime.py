from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PromptGateConfig, load_config
from .guards import apply_guards
from .lexicon import load_configured_lexicon, match_lexicon
from .llm import OpenAIResponsesProvider, PromptGateProvider
from .preflight import analyze_preflight
from .prompts import build_promptgate_request
from .registry import SkillRegistry, load_registry
from .resources import runtime_root
from .result import (
    ResultValidationError,
    build_fallback_result,
    load_result_schema,
    parse_json_document,
    validate_result,
)


def run_promptgate(
    raw_prompt: str,
    provider: PromptGateProvider | None = None,
    project_root: Path | None = None,
    config: PromptGateConfig | None = None,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    root = runtime_root(project_root)
    active_config = config or load_config(root)
    active_registry = registry or load_registry(active_config.registry_path)
    schema = load_result_schema(root)
    active_provider = provider or OpenAIResponsesProvider.from_env()
    preflight = analyze_preflight(raw_prompt)
    lexicon_entries = load_configured_lexicon(active_config)
    lexicon_matches = match_lexicon(raw_prompt, lexicon_entries)
    request = build_promptgate_request(
        raw_prompt,
        active_config,
        active_registry,
        schema,
        preflight=preflight,
        lexicon_matches=lexicon_matches,
    )

    try:
        draft_text = active_provider.complete_json(request)
    except Exception as exc:
        fallback = build_fallback_result(raw_prompt, active_config.mode, f"Provider error: {exc}")
        validate_result(fallback, schema)
        return fallback

    try:
        draft = parse_json_document(draft_text)
        validate_result(draft, schema)
    except Exception as first_error:
        try:
            repaired_text = active_provider.repair_json(request, draft_text, str(first_error))
            draft = parse_json_document(repaired_text)
            validate_result(draft, schema)
        except Exception as repair_error:
            fallback = build_fallback_result(raw_prompt, active_config.mode, f"LLM repair failed: {repair_error}")
            validate_result(fallback, schema)
            return fallback

    guarded = apply_guards(draft, raw_prompt=raw_prompt, config=active_config, registry=active_registry)
    try:
        validate_result(guarded, schema)
    except ResultValidationError as error:
        fallback = build_fallback_result(raw_prompt, active_config.mode, f"Guarded result failed validation: {error}")
        validate_result(fallback, schema)
        return fallback

    return guarded
