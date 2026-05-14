# PromptGate v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PromptGate v0 as a platform-neutral prompt refinement toolkit with external skill handoff contracts for Claude and Codex.

**Architecture:** `core/` is the source of truth for refinement, registry, matching, and output contracts. `adapters/` contains thin Claude/Codex guidance that consumes the core policy without owning separate behavior. `evals/` plus `scripts/validate_evals.py` provide deterministic regression checks before any LLM judge or deterministic platform invocation exists.

**Tech Stack:** Markdown, YAML, JSON Schema, Python 3.11, PyYAML, unittest, Claude Code skills, Codex skills.

---

## Resolved Implementation Decisions

- The first refiner is instruction-only, not backed by an executable model or script.
- The first skill registry is manually configured with optional discovery documented for later.
- Adapter files are hand-maintained in v0 and must cite `core/` as source of truth.
- `scripts/validate_evals.py` performs deterministic schema, handoff, risk, and fake-skill checks.
- Normal user output hides metadata; `debug` mode exposes `PromptGateResult`.

## File Structure and Responsibilities

```text
README.md
  Public overview, quickstart, and v0 boundary.

requirements-dev.txt
  Python development dependencies for eval validation.

promptgate.config.example.yaml
  Example project configuration for mode, risk policy, registry sources, and output visibility.

core/prompt-refiner/SKILL.md
  Canonical PromptGate refiner instructions.

core/prompt-refiner/references/*.md
  Focused references for messy input patterns, context separation, question policy, and output schema.

core/skill-recommender/matching-policy.md
core/skill-recommender/scoring-policy.yaml
  Explainable skill matching and confidence scoring policy.

core/skill-registry/schema.yaml
core/skill-registry/examples.yaml
  Manual registry format and example records.

core/lexicon/default-user-lexicon.yaml
core/lexicon/schema.yaml
  Default Korean-heavy user phrase interpretations and lexicon shape.

core/output-contract/promptgate-result.schema.json
core/output-contract/answer-contract.md
  Canonical result schema and downstream response contract.

adapters/claude/*
  Claude-specific usage instructions, PromptGate skill wrapper, and hook example.

adapters/codex/*
  Codex-specific usage instructions, PromptGate skill wrapper, and hook example.

evals/*.yaml
  Deterministic eval fixtures for refinement, candidate handling, handoff, clarification, and risk.

scripts/validate_evals.py
scripts/validate-evals.py
  Importable validator module and CLI wrapper.

tests/test_validate_evals.py
  Unit tests for deterministic eval validation behavior.

docs/*.md
docs/adr/0001-core-first-thin-adapters.md
  Public documentation and the first architectural decision record.
```

### Task 1: Bootstrap Public Project Files

**Files:**
- Create: `README.md`
- Create: `requirements-dev.txt`
- Create: `promptgate.config.example.yaml`
- Create: `docs/adr/0001-core-first-thin-adapters.md`

- [ ] **Step 1: Create the public README**

Create `README.md` with this content:

```markdown
# PromptGate

PromptGate is a prompt refinement toolkit for AI agent workflows.

It turns rough user prompts into structured, actionable requests and can hand the refined prompt to registered external skills in Claude or Codex environments.

PromptGate does not bundle workflow skills. It does not own coding, research, planning, deployment, or review workflows. It only refines prompts and routes them to skills that already exist in the user's environment.

## Core Idea

```text
PromptGate = Prompt Refinement Engine + External Skill Handoff Layer
```

## v0 Capabilities

- Refine messy prompts into a clear `refined_prompt`.
- Separate goal, background, constraints, exclusions, output preferences, assumptions, and solution candidates.
- Treat solution ideas as candidates, not requirements.
- Prefer explicitly mentioned registered skills over inferred matches.
- Automatically hand off to safe registered skills by default.
- Block high-risk or destructive handoff by policy.
- Provide thin Claude and Codex adapters.
- Validate core behavior with deterministic eval fixtures.

## What PromptGate Does Not Do

- It does not include named workflow skills.
- It does not hardcode downstream skill names.
- It does not run destructive actions automatically.
- It does not guarantee deterministic slash-command invocation across every platform in v0.

## Quickstart

Install development dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Validate eval fixtures:

```bash
python3 scripts/validate-evals.py
```

Read the design spec:

```text
docs/superpowers/specs/2026-05-14-promptgate-design.md
```

## Repository Layout

```text
core/       Platform-neutral PromptGate policy and contracts
adapters/   Thin Claude and Codex adapter guidance
evals/      Deterministic behavior fixtures
scripts/    Validation tooling
docs/       Public documentation and ADRs
```

## License

License choice is intentionally deferred until the repository is ready for public release. Do not publish this repository as open source until `LICENSE` is added.
```

- [ ] **Step 2: Create development requirements**

Create `requirements-dev.txt` with this content:

```text
PyYAML>=6.0.1,<7
```

- [ ] **Step 3: Create the example configuration**

Create `promptgate.config.example.yaml` with this content:

```yaml
promptgate:
  mode: auto
  auto_handoff_threshold: 0.78
  max_recommendations: 3

  skill_registry:
    sources:
      - project
      - user
      - plugin
    registry_path: ./core/skill-registry/examples.yaml

  risk_policy:
    low: auto
    medium: auto
    high: suggest
    destructive: require_confirmation

  output:
    show_refined_prompt: false
    show_handoff_notice: false
    debug_on_keyword: true

  lexicon:
    use_default_korean_lexicon: true
    project_lexicon_path: ./core/lexicon/default-user-lexicon.yaml
```

- [ ] **Step 4: Create the first ADR**

Create `docs/adr/0001-core-first-thin-adapters.md` with this content:

```markdown
# ADR 0001: Core First, Thin Adapters

Date: 2026-05-14

## Status

Accepted

## Context

PromptGate must support Claude and Codex without splitting into two separate products. If each adapter owns its own refinement rules, the same user prompt can produce inconsistent behavior across platforms.

## Decision

PromptGate keeps platform-neutral behavior in `core/`. Claude and Codex adapters are thin consumers of that core policy.

Adapters may explain platform-specific installation, skill discovery, and hook behavior, but they must not introduce separate refinement or matching rules.

## Consequences

- Eval fixtures apply to the shared core contract.
- Adapter drift is easier to detect.
- v0 can support both Claude and Codex without building deterministic invocation for every platform.
- Future generators can be added later without changing the product model.
```

- [ ] **Step 5: Verify files exist**

Run:

```bash
test -f README.md
test -f requirements-dev.txt
test -f promptgate.config.example.yaml
test -f docs/adr/0001-core-first-thin-adapters.md
```

Expected: command exits with status `0`.

- [ ] **Step 6: Commit bootstrap files**

Run:

```bash
git add README.md requirements-dev.txt promptgate.config.example.yaml docs/adr/0001-core-first-thin-adapters.md
git commit -m "docs: add PromptGate project bootstrap"
```

Expected: commit succeeds.

### Task 2: Define Output Contract and Registry Schema

**Files:**
- Create: `core/output-contract/promptgate-result.schema.json`
- Create: `core/output-contract/answer-contract.md`
- Create: `core/skill-registry/schema.yaml`
- Create: `core/skill-registry/examples.yaml`

- [ ] **Step 1: Create the PromptGateResult JSON schema**

Create `core/output-contract/promptgate-result.schema.json` with this content:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://promptgate.dev/schemas/promptgate-result.schema.json",
  "title": "PromptGateResult",
  "type": "object",
  "required": [
    "original_prompt",
    "refined_prompt",
    "intent",
    "context",
    "clarification",
    "skill_handoff",
    "safety"
  ],
  "additionalProperties": false,
  "properties": {
    "original_prompt": { "type": "string", "minLength": 1 },
    "refined_prompt": { "type": "string", "minLength": 1 },
    "intent": {
      "type": "object",
      "required": ["goal", "domain", "task_type", "confidence"],
      "additionalProperties": false,
      "properties": {
        "goal": { "type": "string", "minLength": 1 },
        "domain": { "type": "string", "minLength": 1 },
        "task_type": { "type": "string", "minLength": 1 },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "context": {
      "type": "object",
      "required": [
        "background",
        "constraints",
        "exclusions",
        "output_preferences",
        "solution_candidates",
        "assumptions"
      ],
      "additionalProperties": false,
      "properties": {
        "background": { "type": "array", "items": { "type": "string" } },
        "constraints": { "type": "array", "items": { "type": "string" } },
        "exclusions": { "type": "array", "items": { "type": "string" } },
        "output_preferences": { "type": "array", "items": { "type": "string" } },
        "solution_candidates": { "type": "array", "items": { "type": "string" } },
        "assumptions": { "type": "array", "items": { "type": "string" } }
      }
    },
    "clarification": {
      "type": "object",
      "required": ["needed", "question", "reason"],
      "additionalProperties": false,
      "properties": {
        "needed": { "type": "boolean" },
        "question": { "type": ["string", "null"] },
        "reason": { "type": ["string", "null"] }
      }
    },
    "skill_handoff": {
      "type": "object",
      "required": [
        "mode",
        "explicit_skill_mention",
        "target_skill",
        "target_source",
        "confidence",
        "status",
        "reason"
      ],
      "additionalProperties": false,
      "properties": {
        "mode": { "enum": ["auto", "suggest", "debug", "off"] },
        "explicit_skill_mention": { "type": ["string", "null"] },
        "target_skill": { "type": ["string", "null"] },
        "target_source": { "enum": ["explicit", "matched", "none"] },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "status": {
          "enum": [
            "auto_handoff",
            "suggested",
            "no_match",
            "skill_not_found",
            "blocked_by_risk",
            "disabled"
          ]
        },
        "reason": { "type": ["string", "null"] }
      }
    },
    "safety": {
      "type": "object",
      "required": ["risk_level", "requires_confirmation", "reason"],
      "additionalProperties": false,
      "properties": {
        "risk_level": { "enum": ["low", "medium", "high", "destructive"] },
        "requires_confirmation": { "type": "boolean" },
        "reason": { "type": ["string", "null"] }
      }
    }
  }
}
```

- [ ] **Step 2: Create the answer contract**

Create `core/output-contract/answer-contract.md` with this content:

```markdown
# PromptGate Answer Contract

PromptGate normal output should feel invisible.

In `auto` mode, the user should normally see the downstream response, not PromptGate metadata. Metadata may be injected into agent context for routing, but it should not be printed unless debug output is requested.

## Required Checks

Before a refined prompt is handed off:

- The main goal is explicit.
- Exclusions are preserved.
- Output preferences are preserved.
- Solution candidates remain candidates.
- Registered skill names are not invented.
- High-risk and destructive handoffs follow risk policy.

## Debug Output

When debug output is requested, show:

- `original_prompt`
- `refined_prompt`
- `intent`
- `context`
- `clarification`
- `skill_handoff`
- `safety`

Do not expose hidden platform credentials, local paths outside the project, or private skill contents in debug output.
```

- [ ] **Step 3: Create the skill registry schema**

Create `core/skill-registry/schema.yaml` with this content:

```yaml
skill_registry_schema:
  version: 1
  required_skill_fields:
    - id
    - description
    - aliases
    - domains
    - task_types
    - trigger_phrases
    - risk_level
    - auto_invocable
  optional_skill_fields:
    - platform_names
  risk_levels:
    - low
    - medium
    - high
    - destructive
  id_rules:
    pattern: "^[a-z0-9][a-z0-9._:-]*$"
    description: "Stable skill identifier. May include plugin-style namespaces."
  platform_names:
    claude: "Skill name used in Claude, or null if unavailable."
    codex: "Skill name used in Codex, or null if unavailable."
```

- [ ] **Step 4: Create example registry entries without hardcoded product assumptions**

Create `core/skill-registry/examples.yaml` with this content:

```yaml
skills:
  - id: example-low-risk-skill
    platform_names:
      claude: example-low-risk-skill
      codex: example-low-risk-skill
    description: Example low-risk registered skill for refining a written artifact.
    aliases:
      - polish
      - rewrite
      - 정리
    domains:
      - writing
    task_types:
      - rewrite
      - refine
    trigger_phrases:
      - 정리해줘
      - 자연스럽게
    risk_level: low
    auto_invocable: true

  - id: example-destructive-skill
    platform_names:
      claude: example-destructive-skill
      codex: example-destructive-skill
    description: Example destructive skill used only to validate risk blocking.
    aliases:
      - delete
      - remove permanently
    domains:
      - operations
    task_types:
      - destructive-action
    trigger_phrases:
      - delete everything
      - permanently remove
    risk_level: destructive
    auto_invocable: false
```

- [ ] **Step 5: Verify JSON and YAML parse**

Run:

```bash
python3 -m json.tool core/output-contract/promptgate-result.schema.json >/dev/null
python3 - <<'PY'
import yaml
for path in ["core/skill-registry/schema.yaml", "core/skill-registry/examples.yaml"]:
    with open(path, "r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
print("ok")
PY
```

Expected: prints `ok`.

- [ ] **Step 6: Commit contracts and registry schema**

Run:

```bash
git add core/output-contract core/skill-registry
git commit -m "feat: define PromptGate output and skill registry contracts"
```

Expected: commit succeeds.

### Task 3: Add Canonical Prompt Refiner Skill

**Files:**
- Create: `core/prompt-refiner/SKILL.md`
- Create: `core/prompt-refiner/references/messy-input-patterns.md`
- Create: `core/prompt-refiner/references/context-separation.md`
- Create: `core/prompt-refiner/references/question-policy.md`
- Create: `core/prompt-refiner/references/output-schema.md`

- [ ] **Step 1: Create the canonical refiner skill**

Create `core/prompt-refiner/SKILL.md` with this content:

```markdown
---
name: promptgate
description: Refine rough user prompts into structured actionable requests and hand off to registered external skills when available. Use when the user prompt is vague, mixed, mentions a skill, asks for prompt cleanup, or includes constraints such as "no code" or "direction only".
---

# PromptGate Refiner

You are PromptGate, a prompt refinement engine and external skill handoff layer.

You do not perform downstream workflow work. You refine the user's prompt and decide whether a registered external skill should receive the refined prompt.

## Core Rules

1. Identify the user's main goal before anything else.
2. Separate background, constraints, exclusions, output preferences, assumptions, and solution candidates.
3. Treat solution candidates as candidates, not confirmed requirements.
4. Preserve user exclusions such as "no code", "direction only", "do not implement", and "just summarize".
5. If the user explicitly mentions a registered skill, use that skill as the handoff target.
6. If no skill is explicitly mentioned, match only against registered skills.
7. Never invent a skill name.
8. Default to automatic handoff for low and medium risk skills.
9. Block or suggest high-risk and destructive skills according to risk policy.
10. Ask one clarifying question only when the missing information changes the downstream task materially.

## Required Output

Produce a `PromptGateResult` object internally.

In normal `auto` mode, do not show this object to the user unless debug output is requested. Use it to pass the refined prompt and handoff instruction to the downstream agent or skill.

## References

- `references/messy-input-patterns.md`
- `references/context-separation.md`
- `references/question-policy.md`
- `references/output-schema.md`
```

- [ ] **Step 2: Add messy input patterns**

Create `core/prompt-refiner/references/messy-input-patterns.md` with this content:

```markdown
# Messy Input Patterns

PromptGate should handle rough prompts without criticizing the user.

## Common Patterns

| User Phrase | Interpretation |
|---|---|
| 정리좀 | Keep the meaning, make it clearer and more usable. |
| 방향만 | Prefer strategy, structure, and decision criteria over implementation details. |
| 코드말고 | Exclude code. Answer with architecture, reasoning, or direction only. |
| 별론데 | Identify problems and suggest better direction. |
| 이거 맞아? | Separate correct parts, incorrect parts, and uncertain assumptions. |
| 너무 AI같지 않게 | Remove generic marketing tone, exaggeration, and empty phrases. |
| 구조가 안잡힘 | Clarify goal, actors, scope, and output shape before downstream work. |

## Candidate Language

Phrases like "Redis 쓰면 되나", "이 방법이면 되나", and "X로 하면 어때" usually introduce a candidate solution, not a requirement.

Correct handling:

- Put the candidate in `solution_candidates`.
- Put the underlying need in `goal` or `constraints`.
- Do not force the downstream skill to use the candidate.
```

- [ ] **Step 3: Add context separation rules**

Create `core/prompt-refiner/references/context-separation.md` with this content:

```markdown
# Context Separation

Separate the user's prompt into these fields:

- `goal`: The outcome the user wants.
- `background`: Context that helps interpret the request.
- `constraints`: Requirements the result must satisfy.
- `exclusions`: Things the user does not want.
- `output_preferences`: Desired format, tone, depth, or style.
- `solution_candidates`: Ideas the user mentioned as possible approaches.
- `assumptions`: Reasonable assumptions needed to proceed.

## Rules

1. The goal must be a complete sentence.
2. Exclusions must be copied into the refined prompt.
3. Solution candidates must not be converted into constraints.
4. If the user mentions a skill, remove the skill invocation syntax from `refined_prompt` and keep the rest of the request.
5. The refined prompt must be directly usable by another skill or agent.
```

- [ ] **Step 4: Add question policy**

Create `core/prompt-refiner/references/question-policy.md` with this content:

```markdown
# Question Policy

PromptGate should minimize friction.

Ask a clarifying question only when all of these are true:

1. The missing information materially changes the downstream task.
2. A reasonable assumption would likely produce the wrong result.
3. The request cannot be safely refined without that information.

When asking, ask exactly one question.

Do not ask just to make the prompt more polished. If the user intent is clear enough, refine and continue.

## Examples

No question:

```text
이거 별론데 코드말고 방향만
```

Reason: The user wants direction without code. The target artifact may be implicit, but the exclusion and output preference are clear enough.

One question:

```text
이거 정리해서 보내줘
```

Reason: If there is no visible artifact or recipient context, the downstream output could be an email, report, chat message, or summary. Ask what artifact should be refined.
```

- [ ] **Step 5: Add output schema reference**

Create `core/prompt-refiner/references/output-schema.md` with this content:

```markdown
# Output Schema Reference

PromptGate produces `PromptGateResult`.

Required top-level fields:

- `original_prompt`
- `refined_prompt`
- `intent`
- `context`
- `clarification`
- `skill_handoff`
- `safety`

The canonical machine-readable schema is:

```text
core/output-contract/promptgate-result.schema.json
```

In `auto` mode, the object is internal routing metadata. In `debug` mode, the object may be shown to the user.
```

- [ ] **Step 6: Verify the skill states PromptGate's scope**

Run:

```bash
rg -n "You do not perform downstream workflow work|Never invent a skill name" core/prompt-refiner/SKILL.md
```

Expected: command prints both matching guardrail lines.

- [ ] **Step 7: Commit refiner skill**

Run:

```bash
git add core/prompt-refiner
git commit -m "feat: add canonical PromptGate refiner skill"
```

Expected: commit succeeds.

### Task 4: Add Matching Policy and Lexicon

**Files:**
- Create: `core/skill-recommender/matching-policy.md`
- Create: `core/skill-recommender/scoring-policy.yaml`
- Create: `core/lexicon/default-user-lexicon.yaml`
- Create: `core/lexicon/schema.yaml`

- [ ] **Step 1: Create matching policy documentation**

Create `core/skill-recommender/matching-policy.md` with this content:

```markdown
# Skill Matching Policy

PromptGate recommends or hands off to registered external skills only.

## Priority

1. Explicit skill mention.
2. Safe registered skill with high confidence.
3. Suggested skill when confidence is useful but below auto threshold.
4. Direct refined prompt when no registered skill matches.

## Rules

- Explicit skill mention wins over inferred matches.
- Safety overrides confidence.
- Missing skills are not invented.
- High-risk and destructive skills are not auto-invoked.
- Matching must be explainable in debug mode.

## Handoff Status

| Status | Meaning |
|---|---|
| `auto_handoff` | Safe skill selected automatically. |
| `suggested` | Skill recommended but not auto-invoked. |
| `no_match` | No registered skill matched. |
| `skill_not_found` | User mentioned a skill that is not registered. |
| `blocked_by_risk` | Match exists but risk policy blocks automatic handoff. |
| `disabled` | Handoff mode is off. |
```

- [ ] **Step 2: Create scoring policy**

Create `core/skill-recommender/scoring-policy.yaml` with this content:

```yaml
scoring_policy:
  version: 1
  default_auto_threshold: 0.78
  max_recommendations: 3
  weights:
    explicit_skill_mention: 1.0
    domain_match: 0.24
    task_type_match: 0.24
    alias_match: 0.18
    trigger_phrase_match: 0.18
    description_match: 0.12
  penalties:
    ambiguous_intent: 0.15
    missing_required_registry_fields: 0.4
    high_risk: 0.3
    destructive: 1.0
  rules:
    explicit_mention_sets_target_source: explicit
    risk_policy_overrides_confidence: true
    invent_missing_skills: false
```

- [ ] **Step 3: Create default lexicon**

Create `core/lexicon/default-user-lexicon.yaml` with this content:

```yaml
lexicon:
  - phrase: "정리좀"
    interpretation: "Clarify the request while preserving meaning."
    output_preference: "clear and directly usable"

  - phrase: "방향만"
    interpretation: "Give strategic direction rather than implementation detail."
    output_preference: "direction over code"

  - phrase: "코드말고"
    interpretation: "Exclude code from the downstream response."
    exclusion: "code"

  - phrase: "별론데"
    interpretation: "Identify weaknesses and propose a better direction."
    output_preference: "critique plus recommendation"

  - phrase: "너무 AI같지 않게"
    interpretation: "Avoid generic, exaggerated, or marketing-like phrasing."
    output_preference: "natural and specific"

  - phrase: "구조가 안잡힘"
    interpretation: "Clarify scope, actors, boundaries, and expected output."
    output_preference: "structured framing"
```

- [ ] **Step 4: Create lexicon schema**

Create `core/lexicon/schema.yaml` with this content:

```yaml
lexicon_schema:
  version: 1
  required_fields:
    - phrase
    - interpretation
  optional_fields:
    - output_preference
    - exclusion
    - domain_hint
    - task_type_hint
  rules:
    phrase: "Literal user phrase or short pattern."
    interpretation: "PromptGate's stable interpretation."
    output_preference: "Optional output style implied by the phrase."
    exclusion: "Optional exclusion implied by the phrase."
```

- [ ] **Step 5: Verify policy YAML parses**

Run:

```bash
python3 - <<'PY'
import yaml
paths = [
    "core/skill-recommender/scoring-policy.yaml",
    "core/lexicon/default-user-lexicon.yaml",
    "core/lexicon/schema.yaml",
]
for path in paths:
    with open(path, "r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
print("ok")
PY
```

Expected: prints `ok`.

- [ ] **Step 6: Commit matching and lexicon policy**

Run:

```bash
git add core/skill-recommender core/lexicon
git commit -m "feat: add skill matching policy and default lexicon"
```

Expected: commit succeeds.

### Task 5: Add Eval Fixtures

**Files:**
- Create: `evals/refinement-cases.yaml`
- Create: `evals/candidate-vs-requirement-cases.yaml`
- Create: `evals/skill-handoff-cases.yaml`
- Create: `evals/clarification-cases.yaml`
- Create: `evals/risk-policy-cases.yaml`

- [ ] **Step 1: Create refinement evals**

Create `evals/refinement-cases.yaml` with this content:

```yaml
cases:
  - id: no_code_direction
    input: "이거 별론데 코드말고 방향만"
    expected:
      refined_prompt_includes:
        - "코드는 작성하지 말고"
        - "개선 방향"
      exclusions:
        - "code"
      output_preferences:
        - "direction"
      clarification_needed: false

  - id: natural_rewrite
    input: "이 문장 정리좀 너무 AI같지 않게"
    expected:
      refined_prompt_includes:
        - "자연스럽게"
        - "과장"
      output_preferences:
        - "natural"
      clarification_needed: false
```

- [ ] **Step 2: Create candidate-vs-requirement evals**

Create `evals/candidate-vs-requirement-cases.yaml` with this content:

```yaml
cases:
  - id: redis_candidate_not_requirement
    input: "Redis 쓰면 되나 세션이랑 캐시랑 같이 쓰고 싶은데"
    expected:
      goal_includes:
        - "세션"
        - "캐시"
      solution_candidates:
        - "Redis"
      should_not_assume:
        - "Redis is required"

  - id: framework_candidate_not_requirement
    input: "Next.js로 하면 되나 관리자 페이지 빠르게 만들고 싶은데"
    expected:
      goal_includes:
        - "관리자 페이지"
        - "빠르게"
      solution_candidates:
        - "Next.js"
      should_not_assume:
        - "Next.js is required"
```

- [ ] **Step 3: Create handoff evals**

Create `evals/skill-handoff-cases.yaml` with this content:

```yaml
cases:
  - id: explicit_skill_handoff
    input: "$example-low-risk-skill 이거 정리해서 자연스럽게 만들어줘"
    registered_skills:
      - id: example-low-risk-skill
        risk_level: low
        auto_invocable: true
    expected:
      target_source: explicit
      target_skill: example-low-risk-skill
      status: auto_handoff

  - id: missing_explicit_skill
    input: "$missing-skill 이거 정리해줘"
    registered_skills:
      - id: example-low-risk-skill
        risk_level: low
        auto_invocable: true
    expected:
      target_source: none
      target_skill: null
      status: skill_not_found

  - id: no_fake_skill
    input: "내 의도를 정리해서 맞는 스킬로 보내줘"
    registered_skills: []
    expected:
      target_source: none
      target_skill: null
      status: no_match
```

- [ ] **Step 4: Create clarification evals**

Create `evals/clarification-cases.yaml` with this content:

```yaml
cases:
  - id: needs_artifact_question
    input: "이거 정리해서 보내줘"
    expected:
      clarification_needed: true
      question_count: 1
      question_includes:
        - "어떤 결과물"

  - id: no_question_when_direction_clear
    input: "코드말고 방향만 잡아줘"
    expected:
      clarification_needed: false
      refined_prompt_includes:
        - "코드는 작성하지 말고"
        - "방향"
```

- [ ] **Step 5: Create risk policy evals**

Create `evals/risk-policy-cases.yaml` with this content:

```yaml
cases:
  - id: destructive_skill_block
    input: "$example-destructive-skill 전부 삭제해줘"
    registered_skills:
      - id: example-destructive-skill
        risk_level: destructive
        auto_invocable: false
    expected:
      target_skill: example-destructive-skill
      status: blocked_by_risk
      requires_confirmation: true

  - id: high_risk_skill_suggest
    input: "$release-skill 배포해줘"
    registered_skills:
      - id: release-skill
        risk_level: high
        auto_invocable: true
    expected:
      target_skill: release-skill
      status: blocked_by_risk
      requires_confirmation: true
```

- [ ] **Step 6: Verify all eval YAML parses**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path("evals").glob("*.yaml")):
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data.get("cases"), list), path
print("ok")
PY
```

Expected: prints `ok`.

- [ ] **Step 7: Commit eval fixtures**

Run:

```bash
git add evals
git commit -m "test: add PromptGate eval fixtures"
```

Expected: commit succeeds.

### Task 6: Write Failing Validator Tests

**Files:**
- Create: `tests/test_validate_evals.py`

- [ ] **Step 1: Write unit tests before implementation**

Create `tests/test_validate_evals.py` with this content:

```python
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_evals import EvalValidationError, validate_eval_file


class ValidateEvalsTest(unittest.TestCase):
    def write_case_file(self, payload):
        tempdir = tempfile.TemporaryDirectory()
        path = Path(tempdir.name) / "cases.yaml"
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
        self.addCleanup(tempdir.cleanup)
        return path

    def test_valid_handoff_case_passes(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "explicit_skill_handoff",
                        "input": "$example-skill 정리해줘",
                        "registered_skills": [
                            {
                                "id": "example-skill",
                                "risk_level": "low",
                                "auto_invocable": True,
                            }
                        ],
                        "expected": {
                            "target_source": "explicit",
                            "target_skill": "example-skill",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        validate_eval_file(path)

    def test_fake_skill_fails(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "fake_skill",
                        "input": "맞는 스킬로 보내줘",
                        "registered_skills": [],
                        "expected": {
                            "target_source": "matched",
                            "target_skill": "invented-skill",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "unregistered target_skill"):
            validate_eval_file(path)

    def test_destructive_auto_handoff_fails(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "bad_destructive",
                        "input": "$danger delete",
                        "registered_skills": [
                            {
                                "id": "danger",
                                "risk_level": "destructive",
                                "auto_invocable": True,
                            }
                        ],
                        "expected": {
                            "target_source": "explicit",
                            "target_skill": "danger",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "destructive"):
            validate_eval_file(path)

    def test_clarification_question_count_must_be_one(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "too_many_questions",
                        "input": "이거 정리해서 보내줘",
                        "expected": {
                            "clarification_needed": True,
                            "question_count": 2,
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "question_count"):
            validate_eval_file(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_validate_evals -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.validate_evals'`.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
git add tests/test_validate_evals.py
git commit -m "test: add eval validator unit tests"
```

Expected: commit succeeds with tests present but implementation not yet added.

### Task 7: Implement Eval Validator

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/validate_evals.py`
- Create: `scripts/validate-evals.py`

- [ ] **Step 1: Create import package marker**

Create `scripts/__init__.py` with this content:

```python
"""PromptGate development scripts."""
```

- [ ] **Step 2: Implement validator module**

Create `scripts/validate_evals.py` with this content:

```python
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


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Create CLI wrapper**

Create `scripts/validate-evals.py` with this content:

```python
#!/usr/bin/env python3
from scripts.validate_evals import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run unit tests**

Run:

```bash
python3 -m unittest tests.test_validate_evals -v
```

Expected: all tests pass.

- [ ] **Step 5: Run validator against repository evals**

Run:

```bash
python3 scripts/validate-evals.py
```

Expected: prints `Validated 5 eval file(s).`

- [ ] **Step 6: Commit validator**

Run:

```bash
git add scripts tests
git commit -m "feat: validate PromptGate eval fixtures"
```

Expected: commit succeeds.

### Task 8: Add Claude and Codex Adapters

**Files:**
- Create: `adapters/claude/CLAUDE.md`
- Create: `adapters/claude/skills/promptgate/SKILL.md`
- Create: `adapters/claude/hooks/README.md`
- Create: `adapters/claude/hooks/user-prompt-submit.example.py`
- Create: `adapters/codex/AGENTS.md`
- Create: `adapters/codex/skills/promptgate/SKILL.md`
- Create: `adapters/codex/hooks/README.md`
- Create: `adapters/codex/hooks/user-prompt-submit.example.py`

- [ ] **Step 1: Create Claude adapter instructions**

Create `adapters/claude/CLAUDE.md` with this content:

```markdown
# PromptGate Claude Adapter

Use PromptGate before downstream skill work when the user prompt is vague, mixed, or explicitly mentions a skill.

PromptGate's source of truth is `core/`. This adapter must not define separate refinement rules.

## Default Behavior

- Refine the user prompt.
- Preserve exclusions and output preferences.
- If the user explicitly mentions a registered skill, hand off the refined prompt to that skill.
- If no skill is mentioned, match only registered skills.
- Do not ask the user to confirm low or medium risk handoff.
- Do not auto hand off high-risk or destructive skills.

## Normal Output

Do not print PromptGate metadata unless the user asks for debug output.
```

- [ ] **Step 2: Create Claude PromptGate skill wrapper**

Create `adapters/claude/skills/promptgate/SKILL.md` with this content:

```markdown
---
name: promptgate
description: Refine rough prompts and hand off the refined prompt to registered external skills when appropriate. Use when a user prompt is vague, mixed, includes constraints like no-code, or explicitly mentions a skill.
---

# PromptGate for Claude

Follow the canonical PromptGate policy from:

```text
core/prompt-refiner/SKILL.md
core/output-contract/promptgate-result.schema.json
core/skill-recommender/matching-policy.md
```

## Claude Adapter Rules

1. Use Claude's registered skills as the external skill set.
2. If the user explicitly names a registered skill, treat it as the handoff target.
3. Pass the refined prompt as the downstream skill argument or context.
4. Do not print routing metadata unless debug output is requested.
5. Do not auto hand off high-risk or destructive skills.
```

- [ ] **Step 3: Create Claude hook README**

Create `adapters/claude/hooks/README.md` with this content:

```markdown
# Claude Hook Adapter

This directory contains example hook code for injecting PromptGate context with Claude Code `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic slash-command execution in every Claude setup.

Review and test hook scripts before enabling them.
```

- [ ] **Step 4: Create Claude hook example**

Create `adapters/claude/hooks/user-prompt-submit.example.py` with this content:

```python
#!/usr/bin/env python3
import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    prompt = payload.get("prompt", "")
    additional_context = (
        "PromptGate adapter active. Refine the submitted prompt before downstream work. "
        "If the prompt explicitly names a registered skill, hand off the refined prompt to that skill. "
        "Do not ask for handoff confirmation unless the matched skill is high-risk or destructive. "
        f"Original prompt: {prompt}"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": additional_context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create Codex adapter instructions**

Create `adapters/codex/AGENTS.md` with this content:

```markdown
# PromptGate Codex Adapter

Use PromptGate before downstream skill work when the user prompt is vague, mixed, or explicitly mentions a skill.

PromptGate's source of truth is `core/`. This adapter must not define separate refinement rules.

## Default Behavior

- Refine the user prompt.
- Preserve exclusions and output preferences.
- If the user explicitly mentions a registered skill, hand off the refined prompt to that skill.
- If no skill is mentioned, match only registered skills.
- Do not ask the user to confirm low or medium risk handoff.
- Do not auto hand off high-risk or destructive skills.

## Normal Output

Do not print PromptGate metadata unless the user asks for debug output.
```

- [ ] **Step 6: Create Codex PromptGate skill wrapper**

Create `adapters/codex/skills/promptgate/SKILL.md` with this content:

```markdown
---
name: promptgate
description: Refine rough prompts and hand off the refined prompt to registered external skills when appropriate. Use when a user prompt is vague, mixed, includes constraints like no-code, or explicitly mentions a skill.
---

# PromptGate for Codex

Follow the canonical PromptGate policy from:

```text
core/prompt-refiner/SKILL.md
core/output-contract/promptgate-result.schema.json
core/skill-recommender/matching-policy.md
```

## Codex Adapter Rules

1. Use Codex registered skills as the external skill set.
2. If the user explicitly names a registered skill, treat it as the handoff target.
3. Pass the refined prompt as the downstream skill argument or context.
4. Do not print routing metadata unless debug output is requested.
5. Do not auto hand off high-risk or destructive skills.
```

- [ ] **Step 7: Create Codex hook README**

Create `adapters/codex/hooks/README.md` with this content:

```markdown
# Codex Hook Adapter

This directory contains example hook code for injecting PromptGate context with Codex `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic skill invocation in every Codex setup.

Review and test hook scripts before enabling them.
```

- [ ] **Step 8: Create Codex hook example**

Create `adapters/codex/hooks/user-prompt-submit.example.py` with this content:

```python
#!/usr/bin/env python3
import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    prompt = payload.get("prompt", "")
    additional_context = (
        "PromptGate adapter active. Refine the submitted prompt before downstream work. "
        "If the prompt explicitly names a registered skill, hand off the refined prompt to that skill. "
        "Do not ask for handoff confirmation unless the matched skill is high-risk or destructive. "
        f"Original prompt: {prompt}"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": additional_context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9: Verify adapter scripts parse**

Run:

```bash
python3 -m py_compile adapters/claude/hooks/user-prompt-submit.example.py
python3 -m py_compile adapters/codex/hooks/user-prompt-submit.example.py
```

Expected: command exits with status `0`.

- [ ] **Step 10: Commit adapters**

Run:

```bash
git add adapters
git commit -m "feat: add Claude and Codex PromptGate adapters"
```

Expected: commit succeeds.

### Task 9: Add Public Documentation

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/quickstart.md`
- Create: `docs/configuration.md`
- Create: `docs/compatibility.md`
- Create: `docs/contributing.md`

- [ ] **Step 1: Create architecture docs**

Create `docs/architecture.md` with this content:

```markdown
# PromptGate Architecture

PromptGate has three layers:

1. `core/`: platform-neutral refinement, matching, registry, and output contracts.
2. `adapters/`: Claude and Codex guidance that consumes the core policy.
3. `evals/`: deterministic fixtures that define expected behavior.

The core is the source of truth. Adapters must stay thin and must not introduce separate PromptGate behavior.
```

- [ ] **Step 2: Create quickstart docs**

Create `docs/quickstart.md` with this content:

```markdown
# Quickstart

Install development dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Validate evals:

```bash
python3 scripts/validate-evals.py
```

Use PromptGate manually:

1. Read `core/prompt-refiner/SKILL.md`.
2. Refine the user's prompt into `PromptGateResult`.
3. If a registered safe skill is explicitly mentioned or confidently matched, pass `refined_prompt` to that skill.
4. If no skill matches, use `refined_prompt` directly.
```

- [ ] **Step 3: Create configuration docs**

Create `docs/configuration.md` with this content:

```markdown
# Configuration

PromptGate configuration lives in `promptgate.config.yaml`.

Start from:

```text
promptgate.config.example.yaml
```

## Modes

- `auto`: refine and hand off to safe matched skills.
- `suggest`: refine and show skill recommendations.
- `debug`: show full PromptGate metadata.
- `off`: refine only, no handoff.

## Risk Policy

Low and medium risk skills can be handed off automatically. High-risk and destructive skills require confirmation or suggestion mode.
```

- [ ] **Step 4: Create compatibility docs**

Create `docs/compatibility.md` with this content:

```markdown
# Compatibility

PromptGate v0 supports Claude and Codex through thin adapters.

## Claude

- Uses Claude skill metadata and adapter guidance.
- Can use `UserPromptSubmit` hook context injection where available.
- v0 does not guarantee deterministic slash-command execution in every setup.

## Codex

- Uses Codex skill metadata and adapter guidance.
- Can use `UserPromptSubmit` hook context injection where available.
- v0 does not guarantee deterministic skill invocation in every setup.
```

- [ ] **Step 5: Create contribution docs**

Create `docs/contributing.md` with this content:

```markdown
# Contributing

PromptGate behavior changes should start with eval fixtures.

## Rules

- Do not add named workflow skills to PromptGate core.
- Do not hardcode downstream skill names.
- Add or update eval cases for behavior changes.
- Keep adapters thin.
- Run `python3 scripts/validate-evals.py` before opening a pull request.

## Adding an Eval

Add a case to the relevant file in `evals/`.

Every case needs:

- `id`
- `input`
- non-empty `expected`

Handoff cases that name a target skill must include that skill in `registered_skills`.
```

- [ ] **Step 6: Verify docs preserve PromptGate's scope boundary**

Run:

```bash
rg -n "Do not hardcode downstream skill names|Adapters must stay thin|does not hardcode downstream skill names" docs README.md
```

Expected: command prints matching scope-boundary lines.

- [ ] **Step 7: Commit docs**

Run:

```bash
git add docs README.md
git commit -m "docs: add PromptGate public documentation"
```

Expected: commit succeeds.

### Task 10: Final Verification

**Files:**
- Modify only if previous verification exposes an issue.

- [ ] **Step 1: Run YAML, JSON, and Python validation**

Run:

```bash
python3 -m json.tool core/output-contract/promptgate-result.schema.json >/dev/null
python3 scripts/validate-evals.py
python3 -m unittest tests.test_validate_evals -v
python3 -m py_compile scripts/validate_evals.py scripts/validate-evals.py
```

Expected:

```text
Validated 5 eval file(s).
OK
```

- [ ] **Step 2: Verify scope guardrails are present**

Run:

```bash
rg -n "Do not add named workflow skills|Do not hardcode downstream skill names|Missing skills are not invented" README.md docs core adapters
```

Expected: command prints matching guardrail lines.

- [ ] **Step 3: Verify working tree**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated files may remain untracked. The known pre-existing file is:

```text
?? context-refinement-system-design.md
```

- [ ] **Step 4: Commit any verification fixes**

If Step 1 or Step 2 required fixes, commit them:

```bash
git add <fixed-files>
git commit -m "chore: fix PromptGate v0 verification issues"
```

Expected: no commit is needed if verification already passed.

## Self-Review Checklist

- The plan implements the approved design: prompt refinement, external skill handoff, modes, risk policy, Claude/Codex adapters, evals, and validator.
- The plan does not add bundled workflow skills.
- The plan does not hardcode named downstream workflow skills.
- The plan keeps `core/` as the source of truth.
- The plan includes failing tests before validator implementation.
- The plan uses deterministic validation for v0.
- The plan keeps destructive handoff blocked.
- The plan leaves `context-refinement-system-design.md` untouched because it existed before this work.
