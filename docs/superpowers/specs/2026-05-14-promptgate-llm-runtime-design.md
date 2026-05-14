# PromptGate LLM Runtime Design

Date: 2026-05-14
Status: Approved for implementation planning

## 1. Decision

PromptGate's first executable runtime will be LLM-first with Python contract guards.

The LLM handles natural-language interpretation and produces a draft `PromptGateResult`. Python owns the final product contract: schema validity, registered skill boundaries, risk policy, mode policy, handoff status consistency, repair, fallback, CLI/API shape, and eval execution.

This keeps PromptGate aligned with its product goal: understand rough user prompts better than a regex-only system can, while still preventing the failures that matter most for a routing layer.

## 2. Goals

The runtime must:

1. Accept a raw user prompt and return a valid `PromptGateResult`.
2. Use an LLM to extract intent, separate context, and write `refined_prompt`.
3. Use Python to enforce the canonical schema and safety rules.
4. Never return an unregistered `target_skill`.
5. Never auto hand off high-risk or destructive skills.
6. Support `auto`, `suggest`, `debug`, and `off` modes.
7. Provide deterministic unit tests for guard behavior without calling a real LLM.
8. Provide optional integration tests for real provider behavior when credentials are configured.

## 3. Non-Goals

The first runtime will not:

1. Execute downstream skills directly.
2. Guarantee deterministic skill invocation in Claude or Codex.
3. Build a full deterministic natural-language refiner.
4. Add bundled workflow skills to PromptGate core.
5. Run real LLM calls in default CI.
6. Implement subagent orchestration.
7. Add package-manager distribution.

## 4. Architecture

```text
Raw user prompt
  -> Python loads config, registry, lexicon, schema, scoring policy
  -> Python extracts obvious explicit skill mention hints
  -> Python builds an LLM request package
  -> LLM returns a draft PromptGateResult JSON object
  -> Python parses and validates the draft
  -> Python repairs once when parsing or schema validation fails
  -> Python applies contract guards
  -> Python validates the final result against JSON Schema
  -> Runtime returns PromptGateResult
```

The runtime has two different forms of authority:

```text
LLM authority:
  - Understand the user's natural language.
  - Separate goal, background, constraints, exclusions, preferences, candidates, and assumptions.
  - Write a useful refined_prompt.
  - Suggest clarification when the request cannot be safely refined.
  - Propose an inferred skill match from the registered skill list.

Python authority:
  - Decide whether output is valid JSON.
  - Decide whether output matches PromptGateResult schema.
  - Decide whether a skill is registered.
  - Decide whether risk policy permits handoff.
  - Decide whether config mode permits handoff.
  - Override invalid handoff fields.
  - Return a safe fallback when the LLM result cannot be trusted.
```

## 5. Runtime Modules

The implementation should add a small Python package:

```text
promptgate/
  __init__.py
  cli.py
  config.py
  llm.py
  prompts.py
  registry.py
  result.py
  guards.py
  eval_runner.py
```

### `config.py`

Loads `promptgate.config.yaml` when present and falls back to `promptgate.config.example.yaml` for local development. It exposes mode, auto handoff threshold, max recommendations, registry path, risk policy, output preferences, and lexicon settings.

### `registry.py`

Loads manually configured skill registry YAML. It validates the registry shape, normalizes ids, and provides lookups for `id`, platform names, aliases, and trigger phrases.

### `llm.py`

Defines a provider-neutral interface:

```python
class PromptGateProvider:
    def complete_json(self, request: PromptGateRequest) -> str:
        ...
```

The first concrete provider can be OpenAI-compatible, but the core runtime should depend on this interface rather than directly coupling every module to one provider.

Tests use a fake provider that returns fixed JSON drafts.

### `prompts.py`

Builds the LLM request. The request includes:

- Raw prompt.
- Current mode.
- Available registered skills.
- Risk policy.
- Output schema summary.
- Core PromptGate rules.
- Explicit instruction to return JSON only.

The LLM prompt must tell the model that registered skills are closed-world data: it can choose only from the provided registry.

### `result.py`

Defines typed helpers for `PromptGateResult`, JSON parsing, JSON Schema validation, default fallback result construction, and debug serialization.

### `guards.py`

Applies Python-owned rules after the LLM draft is parsed. Guards may overwrite fields when the correct value is mechanically knowable. If the correct value is not knowable, guards lower risk by clearing handoff and returning `no_match`, `skill_not_found`, `blocked_by_risk`, or `disabled`.

### `eval_runner.py`

Runs existing eval fixtures against the runtime. Default evals use fake provider drafts or deterministic fixture responses. Real provider evals are opt-in and require environment configuration.

### `cli.py`

Provides a local entry point:

```bash
python3 -m promptgate "Redis 쓰면 되나 세션이랑 캐시랑 같이 쓰고 싶은데"
python3 -m promptgate --debug "코드말고 방향만 잡아줘"
python3 -m promptgate eval
```

## 6. Python Guard Rules

Python guards deliberately do not try to understand every natural-language case. They enforce small, strong invariants.

### 6.1 Parse and Schema Guard

Behavior:

1. Parse the LLM response as JSON.
2. Validate required fields and enum values.
3. Clamp numeric confidence values to `0..1` only when the surrounding object is otherwise valid.
4. Run one repair attempt if JSON parsing or schema validation fails.
5. Return fallback result if repair fails.

Fallback result:

```json
{
  "original_prompt": "<raw prompt>",
  "refined_prompt": "<raw prompt>",
  "intent": {
    "goal": "Process the user's request as written.",
    "domain": "general",
    "task_type": "respond",
    "confidence": 0.2
  },
  "context": {
    "background": [],
    "constraints": [],
    "exclusions": [],
    "output_preferences": [],
    "solution_candidates": [],
    "assumptions": []
  },
  "clarification": {
    "needed": false,
    "question": null,
    "reason": "PromptGate used fallback because the LLM result was invalid."
  },
  "skill_handoff": {
    "mode": "<configured mode>",
    "explicit_skill_mention": null,
    "target_skill": null,
    "target_source": "none",
    "confidence": 0,
    "status": "no_match",
    "reason": "Fallback result does not hand off to skills."
  },
  "safety": {
    "risk_level": "low",
    "requires_confirmation": false,
    "reason": null
  }
}
```

### 6.2 Original Prompt Guard

`original_prompt` is always overwritten with the exact raw prompt received by the runtime. The LLM is not allowed to shorten, rewrite, redact, or reinterpret this field.

### 6.3 Explicit Skill Mention Guard

Python extracts explicit skill mentions from the raw prompt before the LLM call. v1 extraction supports direct patterns such as:

```text
$skill-id
@skill-id
/skill-id
```

If an explicit skill mention is present:

1. If the mentioned skill exists in the registry, Python sets `explicit_skill_mention` to that skill id, `target_skill` to that skill id, and `target_source` to `explicit`, unless risk or mode policy later blocks handoff.
2. If the mentioned skill does not exist, Python sets `status` to `skill_not_found`, clears `target_skill`, sets `target_source` to `none`, and sets handoff confidence to `0`.

Explicit mention wins over inferred matches.

### 6.4 Registry Guard

If `target_skill` is not null, it must exist in the loaded registry.

If the LLM returns an unregistered skill:

```text
explicit mention was present:
  status = skill_not_found
  target_skill = null
  target_source = none
  confidence = 0

no explicit mention:
  status = no_match
  target_skill = null
  target_source = none
  confidence = 0
```

The runtime never invents a skill and never preserves an invented skill from the LLM draft.

### 6.5 Risk Guard

The registry is the source of truth for matched skill risk.

Rules:

```text
low:
  auto handoff is allowed when mode and threshold allow it.

medium:
  auto handoff is allowed when mode and threshold allow it.

high:
  auto handoff is not allowed.
  status becomes blocked_by_risk.
  requires_confirmation becomes true.

destructive:
  auto handoff is not allowed.
  status becomes blocked_by_risk.
  requires_confirmation becomes true.
```

If `target_skill` is null, the result-level `safety.risk_level` may use the LLM draft unless it is invalid. Invalid risk values are lowered to `low` only when no skill handoff exists; otherwise the result falls back.

### 6.6 Auto-Invocable Guard

Even low and medium risk skills cannot auto hand off when `auto_invocable` is false.

If a matched skill is not auto-invocable:

```text
mode=auto:
  status = suggested

mode=suggest:
  status = suggested

mode=off:
  status = disabled
```

### 6.7 Mode Guard

Configured mode is authoritative.

```text
mode=off:
  status = disabled
  target_source = none
  target_skill = null
  confidence = 0

mode=suggest:
  auto_handoff is rewritten to suggested

mode=auto:
  auto_handoff is allowed only when skill exists, risk is low/medium, auto_invocable is true, and confidence >= threshold

mode=debug:
  same handoff behavior as auto, but debug output may expose PromptGateResult metadata
```

### 6.8 Target Source Consistency Guard

The handoff fields must be internally consistent.

```text
target_source=none:
  target_skill must be null

target_source=explicit:
  explicit_skill_mention must be non-null
  target_skill must equal explicit_skill_mention

target_source=matched:
  target_skill must be registered
  explicit_skill_mention may be null
```

If consistency cannot be restored mechanically, Python clears handoff and returns `no_match`.

### 6.9 Clarification Guard

If `clarification.needed` is true, `clarification.question` must be a non-empty string. If no valid question exists, Python falls back to a safe generic question:

```text
어떤 결과물을 원하시는지 한 가지만 알려주세요.
```

The schema stores one question string. Eval tests may check that the string is not obviously multiple questions.

### 6.10 Refined Prompt Guard

`refined_prompt` must be non-empty. If the LLM returns an empty or whitespace-only refined prompt, Python uses the raw prompt as the refined prompt and records the fallback reason in `skill_handoff.reason` when possible.

## 7. Repair Strategy

The runtime gets one repair attempt.

Repair input:

- Original raw prompt.
- Invalid LLM output.
- Parse or validation error messages.
- PromptGateResult schema summary.
- Instruction to return corrected JSON only.

If repair succeeds, guards run normally.

If repair fails, the runtime returns the fallback result and does not hand off to any skill.

## 8. Provider Strategy

The runtime should be provider-neutral internally and ship with one concrete adapter first.

The first adapter should support an OpenAI-compatible JSON generation call because it is a practical baseline for structured output. The public runtime API must not assume that all future providers have identical structured-output features. Provider-specific details stay behind `PromptGateProvider`.

Default CI uses fake provider responses, not real API calls.

## 9. Eval Strategy

PromptGate should split evals into three layers.

### 9.1 Fixture Contract Validation

Existing `scripts/validate-evals.py` continues to validate eval fixture shape, expected statuses, registered skill references, and risk constraints.

### 9.2 Guard Evals

New deterministic tests feed fixed LLM drafts into Python guards.

Cases should cover:

- Invalid JSON repair fallback.
- Missing required field repair fallback.
- Unregistered skill from LLM.
- Missing explicit skill.
- High-risk auto handoff blocked.
- Destructive auto handoff blocked.
- `mode=off` disables handoff.
- `mode=suggest` rewrites auto handoff to suggested.
- `auto_invocable=false` prevents auto handoff.
- Empty `refined_prompt` fallback.

### 9.3 Runtime Evals

Runtime evals use fake provider drafts by default. They verify that raw prompt plus a draft response produces the expected final `PromptGateResult`.

Real LLM evals are optional and opt-in:

```text
PROMPTGATE_RUN_LLM_EVALS=1
```

The optional LLM evals should report differences instead of being the default release gate until the project has stable judge criteria.

## 10. Adapter Impact

Claude and Codex adapters remain thin.

The first runtime does not need to guarantee deterministic downstream skill invocation. Adapters can later call the Python runtime from hook scripts and inject the final `PromptGateResult` or `refined_prompt` into context.

Adapter behavior must still cite `core/` as source of truth and must not add separate PromptGate policies.

## 11. CLI Behavior

Default command:

```bash
python3 -m promptgate "raw prompt"
```

Returns user-facing output according to config:

- Normal mode can print only `refined_prompt` plus handoff notice when configured.
- Debug mode prints full `PromptGateResult` JSON.

Machine-readable command:

```bash
python3 -m promptgate --json "raw prompt"
```

Always prints full `PromptGateResult` JSON.

Eval command:

```bash
python3 -m promptgate eval
```

Runs fixture validation and deterministic guard/runtime evals.

## 12. Error Handling

Errors should fail closed.

```text
Provider error:
  return fallback result with no handoff

Config load error:
  report configuration error and exit non-zero in CLI

Registry load error:
  report registry error and exit non-zero in CLI

LLM invalid output:
  repair once, then fallback with no handoff

Guard contradiction:
  clear handoff and return no_match unless explicit missing skill or risk block is known
```

## 13. Acceptance Criteria

The implementation is complete when:

1. A CLI can turn a raw prompt into a valid `PromptGateResult`.
2. The runtime can run with a fake provider in tests.
3. The runtime can run with one real provider when configured.
4. JSON Schema validation is applied to final results.
5. Unregistered skills cannot survive into final `target_skill`.
6. High-risk and destructive skills cannot auto hand off.
7. `mode=off` and `mode=suggest` are enforced by Python.
8. Existing eval fixture validation still passes.
9. New guard tests cover the major policy override paths.
10. Documentation explains that LLM output is a draft and Python guards are authoritative.

## 14. Implementation Order

1. Add runtime package skeleton and config/registry loaders.
2. Add provider interface and fake provider.
3. Add result parsing, schema validation, fallback result builder.
4. Add guard rules.
5. Add LLM prompt builder.
6. Add first real provider adapter.
7. Add CLI.
8. Add deterministic guard tests.
9. Add runtime eval runner using fake provider.
10. Update README and docs with runtime usage.

## 15. Design Constraints

The runtime must preserve PromptGate's existing product boundary:

- PromptGate refines and routes; it does not perform downstream workflows.
- The skill registry is closed-world data.
- Safety overrides confidence.
- Explicit skill mentions win only when the skill is registered and risk policy allows the requested handoff.
- Normal output should avoid exposing metadata unless debug or JSON mode is requested.

