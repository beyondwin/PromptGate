# PromptGate LLM Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an executable PromptGate runtime that turns a raw prompt into a valid `PromptGateResult` using an LLM draft plus Python contract guards.

**Architecture:** Add a small `promptgate/` Python package. The LLM provider produces draft JSON, while Python loads config and registry data, validates schema, applies registry/risk/mode guards, repairs once, and returns a final safe result. Tests use fake providers by default, so CI remains deterministic.

**Tech Stack:** Python 3.11, unittest, PyYAML, jsonschema, optional OpenAI Python SDK, OpenAI Responses API Structured Outputs.

---

## Source Notes

Use the approved spec as the source of product requirements:

```text
docs/superpowers/specs/2026-05-14-promptgate-llm-runtime-design.md
```

OpenAI provider work should follow the current Responses API and Structured Outputs docs:

- `https://developers.openai.com/api/docs/guides/migrate-to-responses`
- `https://developers.openai.com/api/docs/guides/structured-outputs`

The provider code should use Responses API style `client.responses.create`, `response.output_text`, and `text.format` JSON schema configuration. Python must still validate the final object against PromptGate's canonical schema after the provider returns text.

## File Structure

Create and modify these files:

```text
requirements-dev.txt
  Add jsonschema and optional OpenAI SDK dependency.

promptgate/__init__.py
  Package metadata and public runtime export.

promptgate/__main__.py
  Module entry point for `python3 -m promptgate`.

promptgate/config.py
  Load and validate promptgate config.

promptgate/registry.py
  Load and validate skill registry records.

promptgate/result.py
  Parse JSON, load PromptGateResult schema, validate final results, build fallback results, and derive provider-safe schema.

promptgate/llm.py
  Define provider interface, fake provider, and OpenAI Responses provider.

promptgate/prompts.py
  Build provider-neutral prompt requests.

promptgate/guards.py
  Apply Python-owned handoff, risk, mode, clarification, and consistency guards.

promptgate/runtime.py
  Orchestrate config, registry, provider call, repair, guards, final validation, and fallback.

promptgate/eval_runner.py
  Run fixture validation and deterministic runtime guard checks.

promptgate/cli.py
  CLI for prompt execution and eval execution.

tests/test_promptgate_package.py
tests/test_promptgate_config.py
tests/test_promptgate_registry.py
tests/test_promptgate_result.py
tests/test_promptgate_llm.py
tests/test_promptgate_guards.py
tests/test_promptgate_runtime.py
tests/test_promptgate_cli.py
tests/test_promptgate_eval_runner.py
  Focused unittest coverage for each runtime unit.

README.md
docs/quickstart.md
docs/configuration.md
docs/compatibility.md
  Runtime usage documentation.
```

## Task 1: Package Skeleton and Dependencies

**Files:**
- Modify: `requirements-dev.txt`
- Create: `promptgate/__init__.py`
- Create: `promptgate/__main__.py`
- Create: `tests/test_promptgate_package.py`

- [ ] **Step 1: Write the failing package import test**

Create `tests/test_promptgate_package.py`:

```python
import unittest


class PromptGatePackageTest(unittest.TestCase):
    def test_package_exports_version(self):
        import promptgate

        self.assertEqual(promptgate.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the package test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_promptgate_package -v
```

Expected: failure with `ModuleNotFoundError: No module named 'promptgate'`.

- [ ] **Step 3: Add dependencies and package entry points**

Replace `requirements-dev.txt` with:

```text
PyYAML>=6.0.1,<7
jsonschema>=4.23.0,<5
openai>=1.0,<3
```

Create `promptgate/__init__.py`:

```python
__version__ = "0.1.0"

try:
    from .runtime import run_promptgate
except ImportError:
    run_promptgate = None

__all__ = ["__version__", "run_promptgate"]
```

Create `promptgate/__main__.py`:

```python
from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the package test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_promptgate_package -v
```

Expected: `OK`.

- [ ] **Step 5: Commit package skeleton**

Run:

```bash
git add requirements-dev.txt promptgate/__init__.py promptgate/__main__.py tests/test_promptgate_package.py
git commit -m "feat: add PromptGate runtime package skeleton"
```

Expected: commit succeeds.

## Task 2: Config Loader

**Files:**
- Create: `promptgate/config.py`
- Create: `tests/test_promptgate_config.py`

- [ ] **Step 1: Write failing config loader tests**

Create `tests/test_promptgate_config.py`:

```python
import tempfile
import unittest
from pathlib import Path

import yaml

from promptgate.config import ConfigError, PromptGateConfig, load_config


class PromptGateConfigTest(unittest.TestCase):
    def test_loads_example_config_from_project_root(self):
        config = load_config(Path.cwd())

        self.assertEqual(config.mode, "auto")
        self.assertEqual(config.auto_handoff_threshold, 0.78)
        self.assertEqual(config.registry_path, Path.cwd() / "core/skill-registry/examples.yaml")
        self.assertEqual(config.risk_policy["high"], "suggest")

    def test_rejects_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config_path = root / "promptgate.config.yaml"
            config_path.write_text(
                yaml.safe_dump({"promptgate": {"mode": "fast"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "invalid mode"):
                load_config(root)

    def test_defaults_missing_optional_sections(self):
        config = PromptGateConfig.from_mapping(
            {"mode": "suggest"},
            project_root=Path.cwd(),
        )

        self.assertEqual(config.mode, "suggest")
        self.assertEqual(config.auto_handoff_threshold, 0.78)
        self.assertEqual(config.max_recommendations, 3)
        self.assertEqual(config.risk_policy["destructive"], "require_confirmation")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_config -v
```

Expected: failure because `promptgate.config` does not exist.

- [ ] **Step 3: Implement config loader**

Create `promptgate/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


VALID_MODES = {"auto", "suggest", "debug", "off"}
DEFAULT_RISK_POLICY = {
    "low": "auto",
    "medium": "auto",
    "high": "suggest",
    "destructive": "require_confirmation",
}


class ConfigError(ValueError):
    """Raised when PromptGate configuration is invalid."""


@dataclass(frozen=True)
class PromptGateConfig:
    mode: str
    auto_handoff_threshold: float
    max_recommendations: int
    registry_path: Path
    risk_policy: dict[str, str]
    show_refined_prompt: bool
    show_handoff_notice: bool
    debug_on_keyword: bool
    use_default_korean_lexicon: bool
    project_lexicon_path: Path | None

    @classmethod
    def from_mapping(cls, data: dict[str, Any], project_root: Path) -> "PromptGateConfig":
        mode = data.get("mode", "auto")
        if mode not in VALID_MODES:
            raise ConfigError(f"invalid mode {mode!r}; expected one of {sorted(VALID_MODES)}")

        threshold = float(data.get("auto_handoff_threshold", 0.78))
        if not 0 <= threshold <= 1:
            raise ConfigError("auto_handoff_threshold must be between 0 and 1")

        max_recommendations = int(data.get("max_recommendations", 3))
        if max_recommendations < 1:
            raise ConfigError("max_recommendations must be at least 1")

        registry_config = data.get("skill_registry", {})
        registry_path = Path(registry_config.get("registry_path", "./core/skill-registry/examples.yaml"))
        if not registry_path.is_absolute():
            registry_path = project_root / registry_path

        risk_policy = dict(DEFAULT_RISK_POLICY)
        risk_policy.update(data.get("risk_policy", {}))

        output = data.get("output", {})
        lexicon = data.get("lexicon", {})
        lexicon_path_value = lexicon.get("project_lexicon_path")
        lexicon_path = Path(lexicon_path_value) if lexicon_path_value else None
        if lexicon_path is not None and not lexicon_path.is_absolute():
            lexicon_path = project_root / lexicon_path

        return cls(
            mode=mode,
            auto_handoff_threshold=threshold,
            max_recommendations=max_recommendations,
            registry_path=registry_path,
            risk_policy=risk_policy,
            show_refined_prompt=bool(output.get("show_refined_prompt", False)),
            show_handoff_notice=bool(output.get("show_handoff_notice", False)),
            debug_on_keyword=bool(output.get("debug_on_keyword", True)),
            use_default_korean_lexicon=bool(lexicon.get("use_default_korean_lexicon", True)),
            project_lexicon_path=lexicon_path,
        )


def load_config(project_root: Path | None = None) -> PromptGateConfig:
    root = project_root or Path.cwd()
    local_config = root / "promptgate.config.yaml"
    example_config = root / "promptgate.config.example.yaml"
    path = local_config if local_config.exists() else example_config

    if not path.exists():
        raise ConfigError(f"PromptGate config not found at {local_config} or {example_config}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("promptgate"), dict):
        raise ConfigError(f"{path}: expected top-level promptgate mapping")

    return PromptGateConfig.from_mapping(payload["promptgate"], project_root=root)
```

- [ ] **Step 4: Run config tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_config -v
```

Expected: `OK`.

- [ ] **Step 5: Commit config loader**

Run:

```bash
git add promptgate/config.py tests/test_promptgate_config.py
git commit -m "feat: load PromptGate runtime config"
```

Expected: commit succeeds.

## Task 3: Skill Registry Loader

**Files:**
- Create: `promptgate/registry.py`
- Create: `tests/test_promptgate_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/test_promptgate_registry.py`:

```python
import tempfile
import unittest
from pathlib import Path

import yaml

from promptgate.registry import RegistryError, SkillRegistry, load_registry


class PromptGateRegistryTest(unittest.TestCase):
    def test_loads_example_registry(self):
        registry = load_registry(Path("core/skill-registry/examples.yaml"))

        self.assertTrue(registry.has("example-low-risk-skill"))
        self.assertEqual(registry.get("example-destructive-skill").risk_level, "destructive")

    def test_prompt_payload_contains_closed_world_skill_data(self):
        registry = load_registry(Path("core/skill-registry/examples.yaml"))
        payload = registry.as_prompt_payload()

        self.assertEqual(payload[0]["id"], "example-low-risk-skill")
        self.assertIn("risk_level", payload[0])
        self.assertIn("auto_invocable", payload[0])

    def test_rejects_invalid_skill_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "registry.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "skills": [
                            {
                                "id": "-bad",
                                "description": "bad id",
                                "aliases": [],
                                "domains": [],
                                "task_types": [],
                                "trigger_phrases": [],
                                "risk_level": "low",
                                "auto_invocable": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RegistryError, "invalid skill id"):
                load_registry(path)

    def test_registry_can_be_built_from_inline_records(self):
        registry = SkillRegistry.from_records(
            [
                {
                    "id": "writer",
                    "description": "Rewrite text.",
                    "aliases": ["rewrite"],
                    "domains": ["writing"],
                    "task_types": ["rewrite"],
                    "trigger_phrases": ["정리해줘"],
                    "risk_level": "low",
                    "auto_invocable": True,
                }
            ]
        )

        self.assertTrue(registry.has("writer"))
        self.assertEqual(registry.get("writer").aliases, ["rewrite"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_registry -v
```

Expected: failure because `promptgate.registry` does not exist.

- [ ] **Step 3: Implement registry loader**

Create `promptgate/registry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

import yaml


RISK_LEVELS = {"low", "medium", "high", "destructive"}
SKILL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$")


class RegistryError(ValueError):
    """Raised when a skill registry is invalid."""


@dataclass(frozen=True)
class Skill:
    id: str
    description: str
    aliases: list[str]
    domains: list[str]
    task_types: list[str]
    trigger_phrases: list[str]
    risk_level: str
    auto_invocable: bool
    platform_names: dict[str, str | None]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Skill":
        skill_id = data.get("id")
        if not isinstance(skill_id, str) or not SKILL_ID_PATTERN.match(skill_id):
            raise RegistryError(f"invalid skill id {skill_id!r}")

        risk_level = data.get("risk_level")
        if risk_level not in RISK_LEVELS:
            raise RegistryError(f"invalid risk_level {risk_level!r} for {skill_id!r}")

        auto_invocable = data.get("auto_invocable")
        if not isinstance(auto_invocable, bool):
            raise RegistryError(f"auto_invocable must be boolean for {skill_id!r}")

        return cls(
            id=skill_id,
            description=_required_string(data, "description", skill_id),
            aliases=_string_list(data, "aliases", skill_id),
            domains=_string_list(data, "domains", skill_id),
            task_types=_string_list(data, "task_types", skill_id),
            trigger_phrases=_string_list(data, "trigger_phrases", skill_id),
            risk_level=risk_level,
            auto_invocable=auto_invocable,
            platform_names=dict(data.get("platform_names", {})),
        )

    def as_prompt_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "aliases": self.aliases,
            "domains": self.domains,
            "task_types": self.task_types,
            "trigger_phrases": self.trigger_phrases,
            "risk_level": self.risk_level,
            "auto_invocable": self.auto_invocable,
        }


class SkillRegistry:
    def __init__(self, skills: list[Skill]):
        self._skills = list(skills)
        self._by_id = {skill.id: skill for skill in skills}
        if len(self._by_id) != len(skills):
            raise RegistryError("duplicate skill id in registry")

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "SkillRegistry":
        return cls([Skill.from_mapping(record) for record in records])

    def has(self, skill_id: str) -> bool:
        return skill_id in self._by_id

    def get(self, skill_id: str) -> Skill:
        try:
            return self._by_id[skill_id]
        except KeyError as exc:
            raise RegistryError(f"unknown skill {skill_id!r}") from exc

    def as_prompt_payload(self) -> list[dict[str, Any]]:
        return [skill.as_prompt_payload() for skill in self._skills]


def load_registry(path: Path) -> SkillRegistry:
    if not path.exists():
        raise RegistryError(f"registry file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("skills"), list):
        raise RegistryError(f"{path}: expected skills list")

    return SkillRegistry.from_records(payload["skills"])


def _required_string(data: dict[str, Any], field: str, skill_id: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{field} must be a non-empty string for {skill_id!r}")
    return value


def _string_list(data: dict[str, Any], field: str, skill_id: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RegistryError(f"{field} must be a list of strings for {skill_id!r}")
    return value
```

- [ ] **Step 4: Run registry tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_registry -v
```

Expected: `OK`.

- [ ] **Step 5: Commit registry loader**

Run:

```bash
git add promptgate/registry.py tests/test_promptgate_registry.py
git commit -m "feat: load PromptGate skill registry"
```

Expected: commit succeeds.

## Task 4: Result Parsing, Schema Validation, and Fallback

**Files:**
- Create: `promptgate/result.py`
- Create: `tests/test_promptgate_result.py`

- [ ] **Step 1: Write failing result tests**

Create `tests/test_promptgate_result.py`:

```python
import copy
import json
import unittest
from pathlib import Path

from promptgate.result import (
    ResultValidationError,
    build_fallback_result,
    load_result_schema,
    parse_json_document,
    provider_schema,
    validate_result,
)


VALID_RESULT = {
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


class PromptGateResultTest(unittest.TestCase):
    def test_parse_json_document_accepts_plain_json(self):
        parsed = parse_json_document(json.dumps(VALID_RESULT, ensure_ascii=False))

        self.assertEqual(parsed["original_prompt"], "정리좀")

    def test_parse_json_document_accepts_fenced_json(self):
        parsed = parse_json_document("```json\n" + json.dumps(VALID_RESULT, ensure_ascii=False) + "\n```")

        self.assertEqual(parsed["intent"]["domain"], "writing")

    def test_validate_result_accepts_valid_result(self):
        validate_result(VALID_RESULT)

    def test_validate_result_rejects_missing_required_field(self):
        invalid = copy.deepcopy(VALID_RESULT)
        invalid.pop("safety")

        with self.assertRaises(ResultValidationError):
            validate_result(invalid)

    def test_build_fallback_result_is_schema_valid(self):
        result = build_fallback_result("raw prompt", mode="suggest", reason="provider failed")

        self.assertEqual(result["original_prompt"], "raw prompt")
        self.assertEqual(result["refined_prompt"], "raw prompt")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_provider_schema_removes_provider_unsafe_metadata(self):
        schema = provider_schema(load_result_schema(Path.cwd()))

        self.assertNotIn("$schema", schema)
        self.assertNotIn("$id", schema)
        self.assertNotIn("title", schema)
        self.assertEqual(schema["additionalProperties"], False)
        question_schema = schema["properties"]["clarification"]["properties"]["question"]
        self.assertIn("anyOf", question_schema)
        self.assertNotIsInstance(question_schema.get("type"), list)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run result tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_result -v
```

Expected: failure because `promptgate.result` does not exist.

- [ ] **Step 3: Implement result helpers**

Create `promptgate/result.py`:

```python
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError


class ResultValidationError(ValueError):
    """Raised when a PromptGateResult violates the canonical schema."""


def load_result_schema(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or Path.cwd()
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
```

- [ ] **Step 4: Run result tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_result -v
```

Expected: `OK`.

- [ ] **Step 5: Commit result helpers**

Run:

```bash
git add promptgate/result.py tests/test_promptgate_result.py
git commit -m "feat: validate PromptGate runtime results"
```

Expected: commit succeeds.

## Task 5: Provider Interface, Fake Provider, and Prompt Builder

**Files:**
- Create: `promptgate/llm.py`
- Create: `promptgate/prompts.py`
- Create: `tests/test_promptgate_llm.py`

- [ ] **Step 1: Write failing provider and prompt tests**

Create `tests/test_promptgate_llm.py`:

```python
import json
import os
import unittest
from pathlib import Path

from promptgate.config import load_config
from promptgate.llm import FakeProvider, OpenAIResponsesProvider, PromptGateRequest
from promptgate.prompts import build_promptgate_request
from promptgate.registry import load_registry
from promptgate.result import load_result_schema


class PromptGateLLMTest(unittest.TestCase):
    def test_fake_provider_returns_queued_json(self):
        provider = FakeProvider(['{"ok": true}'])
        request = PromptGateRequest(
            system_prompt="system",
            user_prompt="user",
            response_schema={"type": "object"},
            raw_prompt="raw",
        )

        self.assertEqual(provider.complete_json(request), '{"ok": true}')

    def test_fake_provider_raises_when_queue_is_empty(self):
        provider = FakeProvider([])
        request = PromptGateRequest(
            system_prompt="system",
            user_prompt="user",
            response_schema={"type": "object"},
            raw_prompt="raw",
        )

        with self.assertRaisesRegex(RuntimeError, "no fake provider responses"):
            provider.complete_json(request)

    def test_prompt_builder_includes_closed_world_registry(self):
        config = load_config(Path.cwd())
        registry = load_registry(config.registry_path)
        schema = load_result_schema(Path.cwd())

        request = build_promptgate_request(
            raw_prompt="$example-low-risk-skill 정리해줘",
            config=config,
            registry=registry,
            schema=schema,
        )

        self.assertIn("Return JSON only", request.system_prompt)
        self.assertIn("example-low-risk-skill", request.user_prompt)
        self.assertIn("closed-world", request.user_prompt)
        self.assertEqual(request.raw_prompt, "$example-low-risk-skill 정리해줘")

    def test_openai_provider_requires_api_key(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                OpenAIResponsesProvider.from_env()
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run provider tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_llm -v
```

Expected: failure because `promptgate.llm` and `promptgate.prompts` do not exist.

- [ ] **Step 3: Implement provider interface and providers**

Create `promptgate/llm.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol


@dataclass(frozen=True)
class PromptGateRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict
    raw_prompt: str


class PromptGateProvider(Protocol):
    def complete_json(self, request: PromptGateRequest) -> str:
        raise NotImplementedError

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        raise NotImplementedError


class FakeProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def complete_json(self, request: PromptGateRequest) -> str:
        if not self._responses:
            raise RuntimeError("no fake provider responses available")
        return self._responses.pop(0)

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        return self.complete_json(request)


class OpenAIResponsesProvider:
    def __init__(self, api_key: str, model: str = "gpt-5"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    @classmethod
    def from_env(cls) -> "OpenAIResponsesProvider":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required to use the OpenAI provider")
        model = os.environ.get("PROMPTGATE_OPENAI_MODEL", "gpt-5")
        return cls(api_key=api_key, model=model)

    def complete_json(self, request: PromptGateRequest) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "promptgate_result",
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
            store=False,
        )
        return response.output_text

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        repair_request = PromptGateRequest(
            system_prompt=request.system_prompt,
            user_prompt=(
                request.user_prompt
                + "\n\nThe previous JSON output was invalid.\n"
                + f"Validation error: {error}\n"
                + "Return a corrected PromptGateResult JSON object only.\n"
                + "Invalid output:\n"
                + invalid_output
            ),
            response_schema=request.response_schema,
            raw_prompt=request.raw_prompt,
        )
        return self.complete_json(repair_request)
```

- [ ] **Step 4: Implement prompt builder**

Create `promptgate/prompts.py`:

```python
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
```

- [ ] **Step 5: Run provider tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_llm -v
```

Expected: `OK`.

- [ ] **Step 6: Commit provider and prompt builder**

Run:

```bash
git add promptgate/llm.py promptgate/prompts.py tests/test_promptgate_llm.py
git commit -m "feat: add PromptGate LLM provider interface"
```

Expected: commit succeeds.

## Task 6: Python Guard Rules

**Files:**
- Create: `promptgate/guards.py`
- Create: `tests/test_promptgate_guards.py`

- [ ] **Step 1: Write failing guard tests**

Create `tests/test_promptgate_guards.py`:

```python
import copy
import unittest
from pathlib import Path

from promptgate.config import PromptGateConfig, load_config
from promptgate.guards import apply_guards, extract_explicit_skill_mention
from promptgate.registry import SkillRegistry, load_registry
from tests.test_promptgate_result import VALID_RESULT


class PromptGateGuardsTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(Path.cwd())
        self.registry = load_registry(self.config.registry_path)

    def test_extract_explicit_skill_mention(self):
        self.assertEqual(extract_explicit_skill_mention("$example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertEqual(extract_explicit_skill_mention("@example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertEqual(extract_explicit_skill_mention("/example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertIsNone(extract_explicit_skill_mention("정리해줘"))

    def test_original_prompt_is_authoritative(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["original_prompt"] = "changed"

        result = apply_guards(draft, raw_prompt="raw", config=self.config, registry=self.registry)

        self.assertEqual(result["original_prompt"], "raw")

    def test_missing_explicit_skill_becomes_skill_not_found(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "missing-skill"
        draft["skill_handoff"]["target_source"] = "explicit"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="$missing-skill 정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "skill_not_found")
        self.assertIsNone(result["skill_handoff"]["target_skill"])
        self.assertEqual(result["skill_handoff"]["target_source"], "none")

    def test_unregistered_inferred_skill_becomes_no_match(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "invented-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        self.assertIsNone(result["skill_handoff"]["target_skill"])

    def test_destructive_skill_blocks_auto_handoff(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-destructive-skill"
        draft["skill_handoff"]["target_source"] = "explicit"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 1

        result = apply_guards(
            draft,
            raw_prompt="$example-destructive-skill 전부 삭제해줘",
            config=self.config,
            registry=self.registry,
        )

        self.assertEqual(result["skill_handoff"]["status"], "blocked_by_risk")
        self.assertTrue(result["safety"]["requires_confirmation"])
        self.assertEqual(result["safety"]["risk_level"], "destructive")

    def test_suggest_mode_rewrites_auto_handoff(self):
        suggest_config = PromptGateConfig.from_mapping({"mode": "suggest"}, project_root=Path.cwd())
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-low-risk-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 0.95

        result = apply_guards(draft, raw_prompt="정리해줘", config=suggest_config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "suggested")

    def test_off_mode_disables_handoff(self):
        off_config = PromptGateConfig.from_mapping({"mode": "off"}, project_root=Path.cwd())
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-low-risk-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="정리해줘", config=off_config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "disabled")
        self.assertIsNone(result["skill_handoff"]["target_skill"])

    def test_empty_refined_prompt_falls_back_to_raw_prompt(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["refined_prompt"] = " "

        result = apply_guards(draft, raw_prompt="정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["refined_prompt"], "정리해줘")

    def test_missing_clarification_question_gets_generic_question(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["clarification"]["needed"] = True
        draft["clarification"]["question"] = ""

        result = apply_guards(draft, raw_prompt="이거 정리해서 보내줘", config=self.config, registry=self.registry)

        self.assertEqual(result["clarification"]["question"], "어떤 결과물을 원하시는지 한 가지만 알려주세요.")

    def test_auto_invocable_false_prevents_auto_handoff(self):
        registry = SkillRegistry.from_records(
            [
                {
                    "id": "manual-skill",
                    "description": "Manual review skill.",
                    "aliases": [],
                    "domains": ["ops"],
                    "task_types": ["review"],
                    "trigger_phrases": [],
                    "risk_level": "low",
                    "auto_invocable": False,
                }
            ]
        )
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "manual-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 0.99

        result = apply_guards(draft, raw_prompt="검토해줘", config=self.config, registry=registry)

        self.assertEqual(result["skill_handoff"]["status"], "suggested")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run guard tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_guards -v
```

Expected: failure because `promptgate.guards` does not exist.

- [ ] **Step 3: Implement guard rules**

Create `promptgate/guards.py`:

```python
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
```

- [ ] **Step 4: Run guard tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_guards -v
```

Expected: `OK`.

- [ ] **Step 5: Run all focused runtime tests so far**

Run:

```bash
python3 -m unittest tests.test_promptgate_config tests.test_promptgate_registry tests.test_promptgate_result tests.test_promptgate_llm tests.test_promptgate_guards -v
```

Expected: `OK`.

- [ ] **Step 6: Commit guards**

Run:

```bash
git add promptgate/guards.py tests/test_promptgate_guards.py
git commit -m "feat: enforce PromptGate handoff guards"
```

Expected: commit succeeds.

## Task 7: Runtime Orchestration with Repair and Fallback

**Files:**
- Create: `promptgate/runtime.py`
- Modify: `promptgate/__init__.py`
- Create: `tests/test_promptgate_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/test_promptgate_runtime.py`:

```python
import copy
import json
import unittest

from promptgate.llm import FakeProvider
from promptgate.result import validate_result
from promptgate.runtime import run_promptgate
from tests.test_promptgate_result import VALID_RESULT


class PromptGateRuntimeTest(unittest.TestCase):
    def test_run_promptgate_returns_guarded_valid_result(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["original_prompt"] = "wrong"
        draft["skill_handoff"]["target_skill"] = "invented-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        provider = FakeProvider([json.dumps(draft, ensure_ascii=False)])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["original_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_run_promptgate_repairs_once(self):
        repaired = copy.deepcopy(VALID_RESULT)
        repaired["refined_prompt"] = "수정된 JSON 결과"
        provider = FakeProvider(["not json", json.dumps(repaired, ensure_ascii=False)])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "수정된 JSON 결과")
        validate_result(result)

    def test_run_promptgate_falls_back_when_provider_and_repair_fail(self):
        provider = FakeProvider(["not json", "still not json"])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_run_promptgate_falls_back_on_provider_error(self):
        provider = FakeProvider([])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run runtime tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_runtime -v
```

Expected: failure because `promptgate.runtime` does not exist.

- [ ] **Step 3: Implement runtime orchestration**

Create `promptgate/runtime.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PromptGateConfig, load_config
from .guards import apply_guards
from .llm import OpenAIResponsesProvider, PromptGateProvider
from .prompts import build_promptgate_request
from .registry import SkillRegistry, load_registry
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
    root = project_root or Path.cwd()
    active_config = config or load_config(root)
    active_registry = registry or load_registry(active_config.registry_path)
    schema = load_result_schema(root)
    active_provider = provider or OpenAIResponsesProvider.from_env()
    request = build_promptgate_request(raw_prompt, active_config, active_registry, schema)

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
```

Replace `promptgate/__init__.py` with:

```python
__version__ = "0.1.0"

from .runtime import run_promptgate

__all__ = ["__version__", "run_promptgate"]
```

- [ ] **Step 4: Run runtime tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_runtime -v
```

Expected: `OK`.

- [ ] **Step 5: Run package test to verify public export still passes**

Run:

```bash
python3 -m unittest tests.test_promptgate_package -v
```

Expected: `OK`.

- [ ] **Step 6: Commit runtime orchestration**

Run:

```bash
git add promptgate/runtime.py promptgate/__init__.py tests/test_promptgate_runtime.py
git commit -m "feat: run PromptGate LLM runtime"
```

Expected: commit succeeds.

## Task 8: CLI

**Files:**
- Create: `promptgate/cli.py`
- Create: `tests/test_promptgate_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_promptgate_cli.py`:

```python
import json
import unittest

from promptgate.cli import format_result
from tests.test_promptgate_result import VALID_RESULT


class PromptGateCLITest(unittest.TestCase):
    def test_format_result_json_outputs_full_json(self):
        output = format_result(VALID_RESULT, as_json=True, debug=False)
        parsed = json.loads(output)

        self.assertEqual(parsed["original_prompt"], "정리좀")

    def test_format_result_debug_outputs_full_json(self):
        output = format_result(VALID_RESULT, as_json=False, debug=True)
        parsed = json.loads(output)

        self.assertEqual(parsed["skill_handoff"]["status"], "no_match")

    def test_format_result_default_outputs_refined_prompt(self):
        output = format_result(VALID_RESULT, as_json=False, debug=False)

        self.assertEqual(output, "문장을 자연스럽게 정리해줘.")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli -v
```

Expected: failure because `promptgate.cli` does not exist.

- [ ] **Step 3: Implement CLI formatting and command parsing**

Create `promptgate/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .runtime import run_promptgate


def format_result(result: dict[str, Any], as_json: bool, debug: bool) -> str:
    if as_json or debug:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return result["refined_prompt"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PromptGate over a raw prompt.")
    parser.add_argument("prompt", nargs="*", help="Raw prompt to refine, or 'eval' to run evals.")
    parser.add_argument("--json", action="store_true", help="Print full PromptGateResult JSON.")
    parser.add_argument("--debug", action="store_true", help="Print full PromptGateResult JSON.")
    args = parser.parse_args(argv)

    if args.prompt == ["eval"]:
        from .eval_runner import run_eval_suite

        report = run_eval_suite()
        print(report)
        return 0

    raw_prompt = " ".join(args.prompt).strip()
    if not raw_prompt:
        parser.error("prompt is required")

    result = run_promptgate(raw_prompt)
    print(format_result(result, as_json=args.json, debug=args.debug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run CLI tests to verify they pass**

```bash
python3 -m unittest tests.test_promptgate_cli -v
```

Expected: `OK`.

- [ ] **Step 5: Commit CLI formatting**

Run:

```bash
git add promptgate/cli.py tests/test_promptgate_cli.py
git commit -m "feat: add PromptGate CLI formatting"
```

Expected: commit succeeds.

## Task 9: Eval Runner

**Files:**
- Create: `promptgate/eval_runner.py`
- Create: `tests/test_promptgate_eval_runner.py`
- Test: `tests/test_promptgate_cli.py`

- [ ] **Step 1: Write failing eval runner tests**

Create `tests/test_promptgate_eval_runner.py`:

```python
import unittest
from pathlib import Path

from promptgate.eval_runner import run_eval_suite


class PromptGateEvalRunnerTest(unittest.TestCase):
    def test_run_eval_suite_validates_existing_fixtures(self):
        report = run_eval_suite(Path.cwd())

        self.assertIn("Validated 5 eval file(s).", report)
        self.assertIn("Deterministic runtime guard checks passed.", report)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run eval runner tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_runner -v
```

Expected: failure because `promptgate.eval_runner` does not exist.

- [ ] **Step 3: Implement eval runner**

Create `promptgate/eval_runner.py`:

```python
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
```

- [ ] **Step 4: Run eval runner and CLI tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_runner tests.test_promptgate_cli -v
```

Expected: `OK`.

- [ ] **Step 5: Verify CLI eval command works**

Run:

```bash
python3 -m promptgate eval
```

Expected:

```text
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 6: Commit eval runner**

Run:

```bash
git add promptgate/eval_runner.py tests/test_promptgate_eval_runner.py
git commit -m "feat: add PromptGate eval runner"
```

Expected: commit succeeds.

## Task 10: Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `docs/quickstart.md`
- Modify: `docs/configuration.md`
- Modify: `docs/compatibility.md`

- [ ] **Step 1: Update README runtime section**

Modify `README.md` by adding this section after Quickstart install instructions:

```markdown
Run PromptGate over a raw prompt:

```bash
python3 -m promptgate --json "Redis 쓰면 되나 세션이랑 캐시랑 같이 쓰고 싶은데"
```

The executable runtime is LLM-first. The provider creates a draft `PromptGateResult`, and Python validates schema, registry, risk, and mode policy before returning the final result.

By default, tests and CI should use fake providers. Real OpenAI calls require:

```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export PROMPTGATE_OPENAI_MODEL=gpt-5
```

Run all runtime evals:

```bash
python3 -m promptgate eval
```
```

- [ ] **Step 2: Update quickstart runtime usage**

Replace `docs/quickstart.md` with:

```markdown
# Quickstart

Install development dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Validate eval fixtures:

```bash
python3 scripts/validate-evals.py
```

Run deterministic runtime evals:

```bash
python3 -m promptgate eval
```

Run PromptGate manually:

```bash
python3 -m promptgate --json "코드말고 방향만 잡아줘"
```

Real provider calls require:

```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export PROMPTGATE_OPENAI_MODEL=gpt-5
```

PromptGate uses the LLM output as a draft. Python guards enforce the final schema, skill registry, risk policy, and mode policy.
```

- [ ] **Step 3: Update configuration docs**

Append this section to `docs/configuration.md`:

```markdown
## Runtime Provider

PromptGate's runtime is provider-neutral internally. The first real provider uses an OpenAI-compatible Responses API adapter.

Environment variables:

```bash
OPENAI_API_KEY=sk-your-openai-api-key
PROMPTGATE_OPENAI_MODEL=gpt-5
```

Default tests do not call a real provider. They use fake provider responses and Python guard checks.
```

- [ ] **Step 4: Update compatibility docs**

Append this section to `docs/compatibility.md`:

```markdown
## Runtime Boundary

The Python runtime can produce a final `PromptGateResult`, but v0 still does not guarantee deterministic downstream skill invocation in every Claude or Codex setup.

Adapters may call the runtime from hook scripts and inject either `PromptGateResult` or `refined_prompt` into context. They must not add separate matching, risk, or refinement policy outside the shared core.
```

- [ ] **Step 5: Run documentation-adjacent verification**

Run:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
```

Expected:

```text
OK
Validated 5 eval file(s).
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 6: Commit documentation**

Run:

```bash
git add README.md docs/quickstart.md docs/configuration.md docs/compatibility.md
git commit -m "docs: document PromptGate runtime usage"
```

Expected: commit succeeds.

## Task 11: Final Verification

**Files:**
- Verify all files changed by Tasks 1-10.

- [ ] **Step 1: Run complete unit test suite**

Run:

```bash
python3 -m unittest
```

Expected: all tests pass.

- [ ] **Step 2: Run legacy eval fixture validation**

Run:

```bash
python3 scripts/validate-evals.py
```

Expected:

```text
Validated 5 eval file(s).
```

- [ ] **Step 3: Run runtime eval command**

Run:

```bash
python3 -m promptgate eval
```

Expected:

```text
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 4: Run a fake-provider smoke test from Python**

Run:

```bash
python3 - <<'PY'
import json
from promptgate.llm import FakeProvider
from promptgate.runtime import run_promptgate
from promptgate.eval_runner import VALID_DRAFT

provider = FakeProvider([json.dumps(VALID_DRAFT, ensure_ascii=False)])
result = run_promptgate("정리좀", provider=provider)
print(result["refined_prompt"])
print(result["skill_handoff"]["status"])
PY
```

Expected:

```text
문장을 자연스럽게 정리해줘.
no_match
```

- [ ] **Step 5: Inspect git diff**

Run:

```bash
git status --short
git log --oneline -n 8
```

Expected: working tree contains only intentional changes. Existing unrelated untracked files, such as `context-refinement-system-design.md`, remain untouched.

- [ ] **Step 6: Final commit if verification caused documentation or test adjustments**

If Step 1-5 required a correction, commit only the correction files. For example, if runtime and CLI files changed, run:

```bash
git add promptgate/runtime.py promptgate/cli.py
git commit -m "chore: finalize PromptGate runtime verification"
```

Expected: commit succeeds when corrections exist. If no corrections exist, skip this step.

## Self-Review Notes

Spec coverage:

- LLM-first runtime: Tasks 5 and 7.
- Python contract guards: Task 6.
- Schema validation and fallback: Task 4 and Task 7.
- Registered skill boundary: Task 3 and Task 6.
- Risk and mode policy: Task 6.
- Fake-provider deterministic tests: Task 5, Task 7, Task 9.
- CLI/API: Task 8 and Task 9.
- Docs: Task 10.
- Final verification: Task 11.

The plan intentionally keeps downstream skill invocation out of scope. It also keeps real LLM evals out of default CI; the first real provider is available through environment configuration, while deterministic tests use `FakeProvider`.
