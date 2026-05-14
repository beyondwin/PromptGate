# PromptGate Adapter Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the PromptGate Python runtime to Claude and Codex hook adapters, adding lightweight preflight and lexicon support so hook context is generated from real runtime output.

**Architecture:** Add small focused modules for deterministic preflight, lexicon loading, and hook IO. Keep Python guards as the authority for final `PromptGateResult`; preflight and lexicon only provide upstream hints. Claude and Codex adapters become thin wrappers around shared hook IO.

**Tech Stack:** Python 3.11+, stdlib `unittest`, `json`, `dataclasses`, `subprocess`, PyYAML, existing PromptGate runtime modules.

---

## Source Documents

- Spec: `docs/superpowers/specs/2026-05-14-promptgate-adapter-runtime-integration-design.md`
- Parent design: `docs/superpowers/specs/2026-05-14-context-refinement-system-design.md`
- Runtime design: `docs/superpowers/specs/2026-05-14-promptgate-llm-runtime-design.md`

## File Structure

- Create `promptgate/preflight.py`: deterministic clarity, bypass, domain, task, risk flag, and route hint analysis.
- Create `tests/test_promptgate_preflight.py`: unit tests for bypass, messy dev prompt, clear prompt, and design prompt.
- Create `promptgate/lexicon.py`: load and match user lexicon YAML entries.
- Create `tests/test_promptgate_lexicon.py`: unit tests for YAML validation and matching.
- Modify `promptgate/prompts.py`: include preflight and matched lexicon hints in the provider request payload.
- Modify `promptgate/runtime.py`: compute preflight and lexicon matches before building the provider request.
- Modify `tests/test_promptgate_runtime.py`: assert runtime passes preflight and lexicon hints to the provider.
- Create `promptgate/hook_io.py`: shared UserPromptSubmit stdin/stdout handling and context formatting.
- Create `tests/test_promptgate_hook_io.py`: unit tests for hook success, bypass, and runtime failure output.
- Modify `adapters/claude/hooks/user-prompt-submit.example.py`: delegate to `promptgate.hook_io.main`.
- Modify `adapters/codex/hooks/user-prompt-submit.example.py`: delegate to `promptgate.hook_io.main`.
- Create `tests/test_promptgate_adapter_hooks.py`: subprocess tests for both adapter scripts.
- Modify `docs/quickstart.md`, `docs/configuration.md`, `docs/compatibility.md`: document hook runtime behavior and smoke commands.

## Implementation Contract

- Do not change `core/output-contract/promptgate-result.schema.json`.
- Do not make real LLM calls in default tests.
- Do not execute downstream skills from hook scripts.
- Do not require `OPENAI_API_KEY` for hook scripts to emit valid JSON.
- Keep every module importable without optional OpenAI dependency unless a real provider is instantiated.

---

### Task 1: Preflight Decision Model

**Files:**
- Create: `promptgate/preflight.py`
- Create: `tests/test_promptgate_preflight.py`

- [ ] **Step 1: Write the failing preflight tests**

Create `tests/test_promptgate_preflight.py`:

```python
import unittest

from promptgate.preflight import analyze_preflight


class PromptGatePreflightTest(unittest.TestCase):
    def test_bypass_prefix_uses_raw_pass_through(self):
        decision = analyze_preflight("#raw 코드말고 방향만")

        self.assertTrue(decision.bypass)
        self.assertEqual(decision.recommended_next, "raw-pass-through")
        self.assertIn("bypass_prefix", decision.risk_flags)

    def test_messy_dev_prompt_detects_candidate_and_exclusion(self):
        decision = analyze_preflight("코드말고 Redis 쓰면 되나 세션이랑 캐시 같이 쓰고 싶은데")

        self.assertFalse(decision.bypass)
        self.assertTrue(decision.is_vague)
        self.assertEqual(decision.domain_guess, "dev")
        self.assertEqual(decision.task_type_guess, "decide")
        self.assertEqual(decision.recommended_next, "prompt-normalizer")
        self.assertEqual(decision.recommended_skill_hint, "dev-task")
        self.assertIn("exclude_code", decision.risk_flags)
        self.assertIn("solution_candidate", decision.risk_flags)

    def test_clear_prompt_goes_direct(self):
        decision = analyze_preflight("README의 Quickstart 섹션을 5문장으로 요약해줘")

        self.assertFalse(decision.bypass)
        self.assertFalse(decision.is_vague)
        self.assertGreaterEqual(decision.clarity_score, 0.8)
        self.assertEqual(decision.recommended_next, "direct")

    def test_design_direction_prompt_routes_to_design_hint(self):
        decision = analyze_preflight("이 디자인 별론데 코드말고 방향만 잡아줘")

        self.assertTrue(decision.is_vague)
        self.assertEqual(decision.domain_guess, "design")
        self.assertEqual(decision.recommended_skill_hint, "design-brief")
        self.assertIn("exclude_code", decision.risk_flags)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the preflight tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_preflight -v
```

Expected:

```text
ModuleNotFoundError: No module named 'promptgate.preflight'
```

- [ ] **Step 3: Implement the preflight module**

Create `promptgate/preflight.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import re


BYPASS_PREFIXES = ("/raw", "!그대로", "#no-normalize", "#raw")
VALID_DOMAINS = {"writing", "dev", "design", "resume", "research", "product", "general"}
VALID_NEXT = {"raw-pass-through", "direct", "prompt-normalizer"}

VAGUE_PHRASES = (
    "정리좀",
    "방향만",
    "코드말고",
    "별론데",
    "구조가 안잡힘",
    "맞어?",
    "맞아?",
    "먼 차이야",
    "뭐가 나아",
    "어떻게 해야",
)

CODE_EXCLUSION_PHRASES = ("코드말고", "코드 말고", "구현하지 말고", "구현 말고")
DESIGN_TERMS = ("디자인", "UI", "UX", "컬러", "색", "레이아웃", "타이포", "고급스럽")
DEV_TERMS = ("Redis", "API", "DB", "SQL", "코드", "버그", "에러", "테스트", "서버", "캐시", "세션")
RESUME_TERMS = ("이력서", "resume", "경력기술서", "포트폴리오")
RESEARCH_TERMS = ("조사", "리서치", "검색", "자료", "근거")
PRODUCT_TERMS = ("MVP", "제품", "기능", "유저", "사용자 플로우")
WRITING_TERMS = ("문장", "글", "카피", "메일", "요약", "정리")

SOLUTION_CANDIDATE_PATTERN = re.compile(
    r"(쓰면 되나|로 하면 되나|써도 되나|괜찮나|맞나|나을까|어때)"
)


@dataclass(frozen=True)
class PreflightDecision:
    bypass: bool
    clarity_score: float
    is_vague: bool
    domain_guess: str
    task_type_guess: str
    risk_flags: list[str]
    recommended_next: str
    recommended_skill_hint: str | None
    reason: str

    def as_prompt_payload(self) -> dict[str, object]:
        return {
            "bypass": self.bypass,
            "clarity_score": self.clarity_score,
            "is_vague": self.is_vague,
            "domain_guess": self.domain_guess,
            "task_type_guess": self.task_type_guess,
            "risk_flags": list(self.risk_flags),
            "recommended_next": self.recommended_next,
            "recommended_skill_hint": self.recommended_skill_hint,
            "reason": self.reason,
        }


def analyze_preflight(raw_prompt: str) -> PreflightDecision:
    prompt = raw_prompt.strip()
    lowered = prompt.lower()
    flags: list[str] = []

    if _has_bypass_prefix(prompt):
        return PreflightDecision(
            bypass=True,
            clarity_score=1.0,
            is_vague=False,
            domain_guess=_guess_domain(prompt),
            task_type_guess=_guess_task_type(prompt),
            risk_flags=["bypass_prefix"],
            recommended_next="raw-pass-through",
            recommended_skill_hint=None,
            reason="User requested raw pass-through.",
        )

    clarity = 0.86
    if len(prompt) < 18:
        clarity -= 0.18
        flags.append("short_prompt")

    if any(phrase in prompt for phrase in VAGUE_PHRASES):
        clarity -= 0.24
        flags.append("vague_phrase")

    if any(phrase in prompt for phrase in CODE_EXCLUSION_PHRASES):
        clarity -= 0.08
        flags.append("exclude_code")

    if SOLUTION_CANDIDATE_PATTERN.search(prompt):
        clarity -= 0.16
        flags.append("solution_candidate")

    if "?" in prompt or "？" in prompt or lowered.endswith("나"):
        clarity -= 0.06
        flags.append("question_like")

    clarity = round(max(0.0, min(1.0, clarity)), 2)
    is_vague = clarity < 0.8
    domain = _guess_domain(prompt)
    task_type = _guess_task_type(prompt)
    recommended_next = "prompt-normalizer" if is_vague else "direct"

    return PreflightDecision(
        bypass=False,
        clarity_score=clarity,
        is_vague=is_vague,
        domain_guess=domain,
        task_type_guess=task_type,
        risk_flags=_dedupe(flags),
        recommended_next=recommended_next,
        recommended_skill_hint=_skill_hint(domain, task_type) if is_vague else None,
        reason=_reason(is_vague, flags),
    )


def _has_bypass_prefix(prompt: str) -> bool:
    return any(prompt.startswith(prefix) for prefix in BYPASS_PREFIXES)


def _guess_domain(prompt: str) -> str:
    if _contains_any(prompt, DESIGN_TERMS):
        return "design"
    if _contains_any(prompt, DEV_TERMS):
        return "dev"
    if _contains_any(prompt, RESUME_TERMS):
        return "resume"
    if _contains_any(prompt, RESEARCH_TERMS):
        return "research"
    if _contains_any(prompt, PRODUCT_TERMS):
        return "product"
    if _contains_any(prompt, WRITING_TERMS):
        return "writing"
    return "general"


def _guess_task_type(prompt: str) -> str:
    if any(phrase in prompt for phrase in ("쓰면 되나", "로 하면 되나", "맞나", "뭐가 나아")):
        return "decide"
    if any(phrase in prompt for phrase in ("정리", "요약", "자연스럽게")):
        return "rewrite"
    if any(phrase in prompt for phrase in ("방향", "계획", "플랜")):
        return "plan"
    if any(phrase in prompt for phrase in ("왜", "원인", "안됨", "에러")):
        return "analyze"
    return "respond"


def _skill_hint(domain: str, task_type: str) -> str | None:
    if domain == "design":
        return "design-brief"
    if domain == "dev":
        return "dev-task"
    if domain == "resume":
        return "resume-portfolio"
    if domain == "research":
        return "research-analysis"
    if task_type == "rewrite" or domain == "writing":
        return "writing-rewrite"
    if domain == "product":
        return "brainstorming"
    return None


def _contains_any(prompt: str, terms: tuple[str, ...]) -> bool:
    lowered = prompt.lower()
    return any(term.lower() in lowered for term in terms)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _reason(is_vague: bool, flags: list[str]) -> str:
    if not is_vague:
        return "Prompt is clear enough for direct handling."
    if "solution_candidate" in flags:
        return "User mentions a possible solution as a candidate."
    if "exclude_code" in flags:
        return "User includes an exclusion that should be preserved."
    return "Prompt contains shorthand or implicit intent."
```

- [ ] **Step 4: Run the preflight tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_preflight -v
```

Expected:

```text
Ran 4 tests

OK
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add promptgate/preflight.py tests/test_promptgate_preflight.py
git commit -m "feat: add PromptGate preflight analysis"
```

---

### Task 2: User Lexicon Loader

**Files:**
- Create: `promptgate/lexicon.py`
- Create: `tests/test_promptgate_lexicon.py`

- [ ] **Step 1: Write the failing lexicon tests**

Create `tests/test_promptgate_lexicon.py`:

```python
import tempfile
import unittest
from pathlib import Path

from promptgate.config import load_config
from promptgate.lexicon import load_configured_lexicon, load_lexicon, match_lexicon


class PromptGateLexiconTest(unittest.TestCase):
    def test_load_lexicon_reads_entries(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "lexicon.yaml"
            path.write_text(
                """
lexicon:
  - phrase: "코드말고"
    interpretation: "Exclude code."
    exclusion: "code"
""".strip(),
                encoding="utf-8",
            )

            entries = load_lexicon(path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].phrase, "코드말고")
        self.assertEqual(entries[0].exclusion, "code")

    def test_match_lexicon_returns_prompt_payloads(self):
        entries = load_lexicon(Path("core/lexicon/default-user-lexicon.yaml"))

        matches = match_lexicon("코드말고 방향만 잡아줘", entries)
        payloads = [match.as_prompt_payload() for match in matches]

        self.assertIn("코드말고", [payload["phrase"] for payload in payloads])
        self.assertIn("방향만", [payload["phrase"] for payload in payloads])

    def test_load_configured_lexicon_uses_existing_config(self):
        config = load_config(Path.cwd())

        entries = load_configured_lexicon(config)

        self.assertGreaterEqual(len(entries), 1)
        self.assertIn("정리좀", [entry.phrase for entry in entries])

    def test_invalid_lexicon_shape_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "bad.yaml"
            path.write_text("lexicon: wrong", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_lexicon(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the lexicon tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_lexicon -v
```

Expected:

```text
ModuleNotFoundError: No module named 'promptgate.lexicon'
```

- [ ] **Step 3: Implement the lexicon module**

Create `promptgate/lexicon.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any

import yaml

from .config import PromptGateConfig


@dataclass(frozen=True)
class LexiconEntry:
    phrase: str
    interpretation: str
    output_preference: str | None = None
    exclusion: str | None = None


@dataclass(frozen=True)
class LexiconMatch:
    phrase: str
    interpretation: str
    output_preference: str | None
    exclusion: str | None

    def as_prompt_payload(self) -> dict[str, str | None]:
        return {
            "phrase": self.phrase,
            "interpretation": self.interpretation,
            "output_preference": self.output_preference,
            "exclusion": self.exclusion,
        }


def load_lexicon(path: Path) -> list[LexiconEntry]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("lexicon"), list):
        raise ValueError(f"{path}: expected top-level lexicon list")

    entries: list[LexiconEntry] = []
    for index, item in enumerate(payload["lexicon"]):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: lexicon[{index}] must be a mapping")
        phrase = item.get("phrase")
        interpretation = item.get("interpretation")
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError(f"{path}: lexicon[{index}].phrase must be a non-empty string")
        if not isinstance(interpretation, str) or not interpretation.strip():
            raise ValueError(f"{path}: lexicon[{index}].interpretation must be a non-empty string")
        entries.append(
            LexiconEntry(
                phrase=phrase,
                interpretation=interpretation,
                output_preference=_optional_str(item.get("output_preference")),
                exclusion=_optional_str(item.get("exclusion")),
            )
        )
    return entries


def load_configured_lexicon(config: PromptGateConfig) -> list[LexiconEntry]:
    if not config.use_default_korean_lexicon and config.project_lexicon_path is None:
        return []
    if config.project_lexicon_path is None:
        return []
    if not config.project_lexicon_path.exists():
        return []
    return load_lexicon(config.project_lexicon_path)


def match_lexicon(raw_prompt: str, entries: Iterable[LexiconEntry]) -> list[LexiconMatch]:
    matches: list[LexiconMatch] = []
    for entry in entries:
        if entry.phrase in raw_prompt:
            matches.append(
                LexiconMatch(
                    phrase=entry.phrase,
                    interpretation=entry.interpretation,
                    output_preference=entry.output_preference,
                    exclusion=entry.exclusion,
                )
            )
    return matches


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional lexicon fields must be strings when present")
    return value
```

- [ ] **Step 4: Run the lexicon tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_lexicon -v
```

Expected:

```text
Ran 4 tests

OK
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add promptgate/lexicon.py tests/test_promptgate_lexicon.py
git commit -m "feat: load PromptGate user lexicon"
```

---

### Task 3: Prompt Payload Context Injection

**Files:**
- Modify: `promptgate/prompts.py`
- Modify: `promptgate/runtime.py`
- Modify: `tests/test_promptgate_runtime.py`

- [ ] **Step 1: Write the failing runtime prompt-context test**

Append this test to `tests/test_promptgate_runtime.py`:

```python
class CapturingProvider:
    def __init__(self, response):
        self.response = response
        self.request = None

    def complete_json(self, request):
        self.request = request
        return self.response

    def repair_json(self, request, invalid_output, error):
        self.request = request
        return self.response


class PromptGateRuntimeContextTest(unittest.TestCase):
    def test_runtime_includes_preflight_and_lexicon_in_provider_payload(self):
        draft = copy.deepcopy(VALID_RESULT)
        provider = CapturingProvider(json.dumps(draft, ensure_ascii=False))

        run_promptgate("코드말고 Redis 쓰면 되나", provider=provider)

        payload = json.loads(provider.request.user_prompt)
        self.assertEqual(payload["preflight"]["domain_guess"], "dev")
        self.assertIn("solution_candidate", payload["preflight"]["risk_flags"])
        phrases = [item["phrase"] for item in payload["matched_user_lexicon"]]
        self.assertIn("코드말고", phrases)
```

- [ ] **Step 2: Run the runtime context test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_promptgate_runtime.PromptGateRuntimeContextTest -v
```

Expected:

```text
KeyError: 'preflight'
```

- [ ] **Step 3: Update `promptgate/prompts.py`**

Replace `promptgate/prompts.py` with:

```python
from __future__ import annotations

import json
from typing import Any

from .config import PromptGateConfig
from .lexicon import LexiconMatch
from .llm import PromptGateRequest
from .preflight import PreflightDecision
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
Use preflight and matched_user_lexicon as interpretation hints, not as final authority.
"""


def build_promptgate_request(
    raw_prompt: str,
    config: PromptGateConfig,
    registry: SkillRegistry,
    schema: dict[str, Any],
    preflight: PreflightDecision | None = None,
    lexicon_matches: list[LexiconMatch] | None = None,
) -> PromptGateRequest:
    response_schema = provider_schema(schema)
    user_payload = {
        "raw_prompt": raw_prompt,
        "mode": config.mode,
        "auto_handoff_threshold": config.auto_handoff_threshold,
        "risk_policy": config.risk_policy,
        "preflight": preflight.as_prompt_payload() if preflight else None,
        "matched_user_lexicon": [
            match.as_prompt_payload() for match in (lexicon_matches or [])
        ],
        "registered_skills_closed_world": registry.as_prompt_payload(),
        "required_behavior": [
            "Produce a PromptGateResult object.",
            "Treat registered skills as closed-world data.",
            "Use only registered skill ids from registered_skills_closed_world.",
            "Set target_skill to null when no registered skill matches.",
            "Do not auto hand off high-risk or destructive skills.",
            "Make refined_prompt directly usable by a downstream agent or skill.",
            "Preserve lexicon-derived exclusions such as code exclusion.",
        ],
    }

    return PromptGateRequest(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2),
        response_schema=response_schema,
        raw_prompt=raw_prompt,
    )
```

- [ ] **Step 4: Update `promptgate/runtime.py`**

Replace `promptgate/runtime.py` with:

```python
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
    preflight = analyze_preflight(raw_prompt)
    lexicon_entries = load_configured_lexicon(active_config)
    lexicon_matches = match_lexicon(raw_prompt, lexicon_entries)
    active_provider = provider or OpenAIResponsesProvider.from_env()
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
```

- [ ] **Step 5: Run runtime tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_runtime -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add promptgate/prompts.py promptgate/runtime.py tests/test_promptgate_runtime.py
git commit -m "feat: pass preflight and lexicon hints to runtime"
```

---

### Task 4: Shared Hook IO

**Files:**
- Create: `promptgate/hook_io.py`
- Create: `tests/test_promptgate_hook_io.py`

- [ ] **Step 1: Write the failing hook IO tests**

Create `tests/test_promptgate_hook_io.py`:

```python
import io
import json
import unittest

from promptgate.hook_io import (
    build_hook_output,
    extract_prompt,
    format_additional_context,
    run_user_prompt_submit_hook,
)
from tests.test_promptgate_result import VALID_RESULT


class PromptGateHookIOTest(unittest.TestCase):
    def test_extract_prompt_accepts_prompt_key(self):
        self.assertEqual(extract_prompt({"prompt": "정리좀"}), "정리좀")

    def test_extract_prompt_accepts_message_key(self):
        self.assertEqual(extract_prompt({"message": "정리좀"}), "정리좀")

    def test_build_hook_output_uses_user_prompt_submit_shape(self):
        output = build_hook_output("context")

        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"],
            "UserPromptSubmit",
        )
        self.assertEqual(
            output["hookSpecificOutput"]["additionalContext"],
            "context",
        )

    def test_format_additional_context_contains_refined_prompt(self):
        context = format_additional_context(VALID_RESULT)

        self.assertIn("PromptGate runtime result", context)
        self.assertIn("문장을 자연스럽게 정리해줘.", context)
        self.assertIn("no_match", context)

    def test_bypass_prompt_does_not_call_runner(self):
        def runner(*args, **kwargs):
            raise AssertionError("runner should not be called")

        stdin = io.StringIO(json.dumps({"prompt": "#raw 그대로"}))
        stdout = io.StringIO()

        exit_code = run_user_prompt_submit_hook(stdin, stdout, runner=runner)

        self.assertEqual(exit_code, 0)
        parsed = json.loads(stdout.getvalue())
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate bypass active", context)

    def test_runtime_failure_still_emits_valid_json(self):
        def runner(*args, **kwargs):
            raise RuntimeError("provider missing")

        stdin = io.StringIO(json.dumps({"prompt": "코드말고 방향만"}))
        stdout = io.StringIO()

        exit_code = run_user_prompt_submit_hook(stdin, stdout, runner=runner)

        self.assertEqual(exit_code, 0)
        parsed = json.loads(stdout.getvalue())
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("provider missing", context)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the hook IO tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_hook_io -v
```

Expected:

```text
ModuleNotFoundError: No module named 'promptgate.hook_io'
```

- [ ] **Step 3: Implement shared hook IO**

Create `promptgate/hook_io.py`:

```python
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
```

- [ ] **Step 4: Run the hook IO tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_hook_io -v
```

Expected:

```text
Ran 6 tests

OK
```

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add promptgate/hook_io.py tests/test_promptgate_hook_io.py
git commit -m "feat: add PromptGate hook IO adapter"
```

---

### Task 5: Claude and Codex Hook Wrappers

**Files:**
- Modify: `adapters/claude/hooks/user-prompt-submit.example.py`
- Modify: `adapters/codex/hooks/user-prompt-submit.example.py`
- Create: `tests/test_promptgate_adapter_hooks.py`

- [ ] **Step 1: Write the failing adapter subprocess tests**

Create `tests/test_promptgate_adapter_hooks.py`:

```python
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptGateAdapterHookTest(unittest.TestCase):
    def test_codex_hook_emits_valid_json_without_openai_key(self):
        output = self._run_hook("adapters/codex/hooks/user-prompt-submit.example.py")

        parsed = json.loads(output)
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("Original prompt", context)

    def test_claude_hook_emits_valid_json_without_openai_key(self):
        output = self._run_hook("adapters/claude/hooks/user-prompt-submit.example.py")

        parsed = json.loads(output)
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("Original prompt", context)

    def test_codex_hook_bypass_path(self):
        output = self._run_hook(
            "adapters/codex/hooks/user-prompt-submit.example.py",
            prompt="#raw 그대로",
        )

        parsed = json.loads(output)
        self.assertIn(
            "PromptGate bypass active",
            parsed["hookSpecificOutput"]["additionalContext"],
        )

    def _run_hook(self, script_path, prompt="코드말고 방향만"):
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / script_path)],
            input=json.dumps({"prompt": prompt}, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=env,
            check=True,
        )
        self.assertEqual(completed.stderr, "")
        return completed.stdout


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the adapter tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_adapter_hooks -v
```

Expected:

```text
AssertionError: 'PromptGate runtime unavailable' not found
```

- [ ] **Step 3: Replace the Codex hook script**

Replace `adapters/codex/hooks/user-prompt-submit.example.py` with:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from promptgate.hook_io import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Replace the Claude hook script**

Replace `adapters/claude/hooks/user-prompt-submit.example.py` with:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from promptgate.hook_io import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the adapter tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_adapter_hooks -v
```

Expected:

```text
Ran 3 tests

OK
```

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add adapters/claude/hooks/user-prompt-submit.example.py adapters/codex/hooks/user-prompt-submit.example.py tests/test_promptgate_adapter_hooks.py
git commit -m "feat: wire PromptGate runtime into adapter hooks"
```

---

### Task 6: Documentation Update

**Files:**
- Modify: `docs/quickstart.md`
- Modify: `docs/configuration.md`
- Modify: `docs/compatibility.md`

- [ ] **Step 1: Update `docs/quickstart.md`**

Append:

````markdown

## Hook Smoke Test

The example Claude and Codex hooks read a `UserPromptSubmit` JSON payload from stdin and emit hook JSON on stdout.

Codex example:

```bash
printf '{"prompt":"코드말고 Redis 쓰면 되나"}' | python3 adapters/codex/hooks/user-prompt-submit.example.py
```

Claude example:

```bash
printf '{"prompt":"코드말고 Redis 쓰면 되나"}' | python3 adapters/claude/hooks/user-prompt-submit.example.py
```

If `OPENAI_API_KEY` is not configured, the hooks still emit valid JSON and preserve the original prompt as raw input.
````

- [ ] **Step 2: Update `docs/configuration.md`**

Append:

````markdown

## Lexicon

PromptGate can load a user lexicon from config:

```yaml
promptgate:
  lexicon:
    use_default_korean_lexicon: true
    project_lexicon_path: ./core/lexicon/default-user-lexicon.yaml
```

Matched lexicon entries are sent to the provider as interpretation hints. Python guards still own final schema, skill registry, risk, and handoff policy.
````

- [ ] **Step 3: Update `docs/compatibility.md`**

Append:

````markdown

## Hook Runtime Compatibility

The example hook scripts are advisory integration points. They inject `additionalContext` generated by the PromptGate runtime, but they do not execute downstream skills directly.

The hook output shape is:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "PromptGate runtime result..."
  }
}
```

When the provider is unavailable, hooks emit valid JSON with a raw-pass-through context so prompt submission is not blocked.
````

- [ ] **Step 4: Commit Task 6**

Run:

```bash
git add docs/quickstart.md docs/configuration.md docs/compatibility.md
git commit -m "docs: document PromptGate hook runtime integration"
```

---

### Task 7: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run the full unit test suite**

Run:

```bash
python3 -m unittest
```

Expected:

```text
OK
```

- [ ] **Step 2: Validate eval fixtures**

Run:

```bash
python3 scripts/validate-evals.py
```

Expected:

```text
Validated 5 eval file(s).
```

- [ ] **Step 3: Run deterministic runtime evals**

Run:

```bash
python3 -m promptgate eval
```

Expected:

```text
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 4: Compile changed Python files**

Run:

```bash
python3 -m py_compile promptgate/preflight.py promptgate/lexicon.py promptgate/hook_io.py adapters/claude/hooks/user-prompt-submit.example.py adapters/codex/hooks/user-prompt-submit.example.py
```

Expected:

```text
No output and exit code 0.
```

- [ ] **Step 5: Run hook smoke commands without credentials**

Run:

```bash
env -u OPENAI_API_KEY zsh -lc 'printf '"'"'{"prompt":"#raw 그대로"}'"'"' | python3 adapters/codex/hooks/user-prompt-submit.example.py'
env -u OPENAI_API_KEY zsh -lc 'printf '"'"'{"prompt":"코드말고 방향만"}'"'"' | python3 adapters/claude/hooks/user-prompt-submit.example.py'
```

Expected:

```text
Both commands print valid JSON with hookSpecificOutput.additionalContext.
The first output contains "PromptGate bypass active".
The second output contains "PromptGate runtime unavailable".
```

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short --branch
```

Expected:

```text
## <branch-name>
```

No untracked or modified files remain except intentional committed changes.

- [ ] **Step 7: Commit final verification note only if docs changed during verification**

If no files changed during verification, do not create another commit. If documentation needed a correction after verification, run:

```bash
git add docs/quickstart.md docs/configuration.md docs/compatibility.md
git commit -m "docs: clarify PromptGate hook verification"
```

## Self-Review

Spec coverage:

- Preflight bypass, clarity, domain, task, and flags are covered by Task 1.
- Lexicon loading and matching are covered by Task 2.
- Runtime prompt injection is covered by Task 3.
- Hook IO success, bypass, and failure paths are covered by Task 4.
- Claude and Codex hook integration is covered by Task 5.
- Public docs are covered by Task 6.
- Full verification is covered by Task 7.

Placeholder scan:

- The plan contains no placeholder implementation steps.
- Every code-producing step includes concrete code.
- Every verification step has a command and expected result.

Type consistency:

- `PreflightDecision.as_prompt_payload()` is consumed by `build_promptgate_request`.
- `LexiconMatch.as_prompt_payload()` is consumed by `build_promptgate_request`.
- `run_user_prompt_submit_hook` accepts an injectable `runner`, which is used by unit tests and defaults to `run_promptgate`.
