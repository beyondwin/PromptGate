# PromptGate Adapter Runtime Integration Design

Date: 2026-05-14
Status: Ready for implementation planning

## 1. Goal

PromptGate already has a Python runtime that can produce and guard a `PromptGateResult`. The next implementation connects that runtime to the Claude and Codex hook adapters and adds the missing lightweight context-refinement pieces needed before the LLM call:

```text
UserPromptSubmit payload
  -> lightweight preflight
  -> optional bypass
  -> lexicon match
  -> PromptGate runtime
  -> hook additionalContext
  -> downstream agent response
```

The target outcome is that the example hook scripts stop injecting a static advisory sentence and instead inject a concrete runtime-derived context block containing the original prompt, refined prompt, handoff status, and safety constraints.

## 2. Current State

The repository currently has:

- `promptgate/runtime.py`: orchestrates config, registry, provider, JSON parsing, repair, schema validation, and guards.
- `promptgate/prompts.py`: builds the LLM request from raw prompt, config, registry, and schema.
- `promptgate/config.py`: loads `promptgate.config.yaml` or `promptgate.config.example.yaml`.
- `promptgate/guards.py`: enforces original prompt, explicit skill mention, registered skill, mode, confidence, and risk rules.
- `promptgate/result.py`: parses and validates `PromptGateResult`, builds fallback results.
- `adapters/claude/hooks/user-prompt-submit.example.py`: reads stdin and emits static `additionalContext`.
- `adapters/codex/hooks/user-prompt-submit.example.py`: reads stdin and emits static `additionalContext`.
- `core/lexicon/default-user-lexicon.yaml`: contains user phrase interpretations, but runtime does not use it yet.

The missing pieces are:

- A deterministic lightweight preflight layer.
- A runtime lexicon loader and matcher.
- A shared hook IO adapter.
- Adapter hook scripts that call the runtime.
- Tests proving hooks do not crash when the provider is unavailable.

## 3. Scope

### In Scope

- Add `promptgate/preflight.py`.
- Add `promptgate/lexicon.py`.
- Add `promptgate/hook_io.py`.
- Include preflight and lexicon matches in the LLM request payload.
- Update Claude and Codex example hook scripts to delegate to shared hook IO.
- Add deterministic unit tests for preflight, lexicon, prompt payload, hook IO, and adapter scripts.
- Update docs with real hook usage and failure behavior.

### Out of Scope

- Executing downstream skills directly.
- Modifying the canonical `PromptGateResult` JSON schema.
- Making real LLM calls part of default tests.
- Adding a packaged installer.
- Guaranteeing slash-command invocation across every Claude or Codex setup.
- Adding router/domain-skill implementations such as `writing-rewrite`, `dev-task`, or `design-brief`.

## 4. Design Decisions

### Decision 1: Preflight Is Deterministic and Small

Preflight must not call an LLM. It runs before provider selection and answers only these questions:

- Should PromptGate bypass normalization?
- Is the prompt likely vague or mixed?
- What domain and task type are likely?
- What lightweight flags should the LLM see?
- Which next path should the hook prefer?

Preflight returns a typed `PreflightDecision`, not a `PromptGateResult`.

### Decision 2: Bypass Happens in Hook IO

The Python runtime remains the contract-enforcing path for normal prompts. Hook IO can bypass the runtime when users explicitly request raw pass-through:

```text
/raw 그대로 실행해
!그대로 이 문장만 답해
#no-normalize Redis 쓰면 되나?
#raw 코드말고 방향만
```

For bypassed prompts, hook IO emits a minimal context block that tells the downstream agent not to normalize and to treat the prompt as raw user intent.

### Decision 3: Lexicon Is Prompt Context, Not a Guard

The user lexicon helps the LLM interpret shorthand phrases. It does not override Python guards. For example, `코드말고` can be sent to the model as an exclusion hint, but the canonical safety and handoff state still comes from schema validation and `apply_guards`.

### Decision 4: Shared Hook IO Owns Platform-Neutral Formatting

Claude and Codex example hooks currently have duplicated static logic. They should become thin wrappers:

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from promptgate.hook_io import main

if __name__ == "__main__":
    raise SystemExit(main())
```

The shared hook IO module owns:

- stdin JSON parsing
- prompt extraction
- preflight bypass
- runtime invocation
- additionalContext formatting
- stdout JSON emission
- non-crashing fallback output

### Decision 5: Provider Failure Must Not Break UserPromptSubmit

Hook execution is on the critical input path. If `OPENAI_API_KEY` is missing, OpenAI import fails, provider returns invalid JSON, config is absent, or any unexpected exception occurs, the hook must still emit valid JSON output.

The fallback output must preserve the original prompt and state that PromptGate could not refine it.

## 5. Module Contracts

### `promptgate/preflight.py`

Exports:

```python
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
        ...


def analyze_preflight(raw_prompt: str) -> PreflightDecision:
    ...
```

Allowed `recommended_next` values:

- `raw-pass-through`
- `direct`
- `prompt-normalizer`

Allowed domain guesses:

- `writing`
- `dev`
- `design`
- `resume`
- `research`
- `product`
- `general`

### `promptgate/lexicon.py`

Exports:

```python
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

    def as_prompt_payload(self) -> dict[str, str]:
        ...


def load_lexicon(path: Path) -> list[LexiconEntry]:
    ...


def load_configured_lexicon(config: PromptGateConfig) -> list[LexiconEntry]:
    ...


def match_lexicon(raw_prompt: str, entries: Iterable[LexiconEntry]) -> list[LexiconMatch]:
    ...
```

Lexicon matching is substring-based in this step. That is enough for Korean shorthand phrases already stored in `core/lexicon/default-user-lexicon.yaml`.

### `promptgate/prompts.py`

`build_promptgate_request` gains optional inputs:

```python
def build_promptgate_request(
    raw_prompt: str,
    config: PromptGateConfig,
    registry: SkillRegistry,
    schema: dict[str, Any],
    preflight: PreflightDecision | None = None,
    lexicon_matches: list[LexiconMatch] | None = None,
) -> PromptGateRequest:
    ...
```

The LLM user payload gains:

```json
{
  "preflight": {
    "bypass": false,
    "clarity_score": 0.46,
    "is_vague": true,
    "domain_guess": "dev",
    "task_type_guess": "decide",
    "risk_flags": ["solution_candidate"],
    "recommended_next": "prompt-normalizer",
    "recommended_skill_hint": "dev-task",
    "reason": "User mentions a possible technology as a candidate."
  },
  "matched_user_lexicon": [
    {
      "phrase": "코드말고",
      "interpretation": "Exclude code from the downstream response.",
      "output_preference": null,
      "exclusion": "code"
    }
  ]
}
```

### `promptgate/runtime.py`

Runtime computes preflight and lexicon matches before building the LLM request:

```text
raw_prompt
  -> analyze_preflight
  -> load_configured_lexicon
  -> match_lexicon
  -> build_promptgate_request(..., preflight, lexicon_matches)
```

Runtime does not bypass provider calls. Bypass is hook behavior so CLI `--json` can still be used for debugging a raw prompt if desired.

### `promptgate/hook_io.py`

Exports:

```python
def extract_prompt(payload: Mapping[str, object]) -> str:
    ...


def format_additional_context(
    result: Mapping[str, object],
    preflight: PreflightDecision | None = None,
    runtime_error: str | None = None,
) -> str:
    ...


def build_hook_output(additional_context: str) -> dict[str, object]:
    ...


def run_user_prompt_submit_hook(
    stdin: TextIO,
    stdout: TextIO,
    project_root: Path | None = None,
    provider: PromptGateProvider | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    ...


def main() -> int:
    ...
```

The stdout shape remains:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "..."
  }
}
```

## 6. Hook Context Format

Normal runtime success:

```text
PromptGate runtime result:
- Original prompt: 코드말고 Redis 쓰면 되나 세션이랑 캐시 같이 쓰고 싶은데
- Refined prompt: Redis is a candidate, not a confirmed requirement. Evaluate session and cache architecture options without writing code.
- Intent: dev / decide
- Handoff: no_match
- Safety: low, confirmation required: false

Use the refined prompt as the downstream request. Preserve exclusions and do not treat solution candidates as requirements.
```

Bypass:

```text
PromptGate bypass active.
Use the user's prompt as raw input without normalization or skill handoff.
Original prompt: #raw 코드말고 방향만
```

Runtime failure:

```text
PromptGate runtime unavailable.
Use the user's prompt as raw input. Do not invent a skill handoff.
Original prompt: 코드말고 방향만
Reason: OPENAI_API_KEY is required to use the OpenAI provider
```

## 7. Test Strategy

Default tests must be deterministic and credential-free:

- Preflight tests use raw strings only.
- Lexicon tests use temporary YAML files and the committed default lexicon.
- Prompt payload tests use `FakeProvider` or inspect `build_promptgate_request`.
- Hook IO tests inject a fake runner or `FakeProvider`.
- Adapter script tests execute each script as a subprocess with JSON stdin and no OpenAI credentials, expecting valid JSON stdout.

Required verification:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
python3 -m py_compile promptgate/preflight.py promptgate/lexicon.py promptgate/hook_io.py adapters/claude/hooks/user-prompt-submit.example.py adapters/codex/hooks/user-prompt-submit.example.py
```

Expected final state:

- All tests pass without `OPENAI_API_KEY`.
- Hook scripts emit valid JSON even without provider credentials.
- `python3 -m promptgate eval` still passes.
- `git status --short` is clean after commit.

## 8. Acceptance Criteria

This implementation is complete when:

1. `analyze_preflight("/raw 그대로 실행해")` returns `bypass=True` and `recommended_next="raw-pass-through"`.
2. `analyze_preflight("코드말고 Redis 쓰면 되나")` returns a dev-oriented vague decision with `solution_candidate` and `exclude_code` flags.
3. `load_configured_lexicon` loads `core/lexicon/default-user-lexicon.yaml` through existing config.
4. `build_promptgate_request` includes `preflight` and `matched_user_lexicon` keys.
5. Shared hook IO emits valid UserPromptSubmit JSON for success, bypass, and runtime failure paths.
6. Claude and Codex example hook scripts use shared hook IO instead of duplicated static text.
7. Documentation explains how to test the hook with JSON stdin.
