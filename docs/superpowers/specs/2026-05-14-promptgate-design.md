# PromptGate Design

Date: 2026-05-14
Status: Approved for v0 planning

## 1. Product Definition

PromptGate is an open-source prompt refinement toolkit for AI agent workflows.

Its job is to take an imperfect user prompt, clarify the intent, separate useful context from noise, and hand off the refined request to a registered external skill when appropriate.

PromptGate is not a workflow skill library. It does not own product brainstorming, plan review, implementation, research, deployment, or any other downstream workflow. It only refines prompts and routes refined prompts to skills that already exist in the user's Claude or Codex environment.

The core product statement is:

```text
PromptGate = Prompt Refinement Engine + External Skill Handoff Layer
```

v0 proves five things:

1. A rough user prompt can be converted into a structured, usable request.
2. Goals, background, constraints, exclusions, output preferences, and solution candidates can be separated reliably.
3. User-mentioned solution candidates are not treated as confirmed requirements.
4. Registered external skills can be recommended or selected without hardcoding specific workflow skills.
5. Claude and Codex can use the same core policy through thin adapters.

## 2. Scope

### In Scope

- Refine user prompts.
- Separate goal, background, constraints, exclusions, output preferences, assumptions, and solution candidates.
- Generate one clarifying question only when the request cannot be safely refined.
- Read or accept a registry view of available external skills.
- Match refined prompts to registered skills.
- Prefer explicitly mentioned skills over inferred matches.
- Automatically hand off to safe matched skills by default.
- Provide `auto`, `suggest`, `debug`, and `off` modes.
- Provide Claude and Codex adapter guidance.
- Validate behavior with eval fixtures.

### Out of Scope

- Bundling specific workflow skills.
- Hardcoding named workflow skills.
- Running downstream workflows directly.
- Implementing product design, plan review, coding, research, or deployment behavior.
- Deterministic slash-command invocation across every platform in v0.
- LLM judge based CI in v0.
- Subagent orchestration.
- Automatic destructive actions.

## 3. Repository Architecture

PromptGate uses a common core with thin platform adapters.

```text
PromptGate/
  README.md
  LICENSE
  AGENTS.md
  CLAUDE.md
  promptgate.config.example.yaml

  core/
    prompt-refiner/
      SKILL.md
      references/
        messy-input-patterns.md
        context-separation.md
        question-policy.md
        output-schema.md

    skill-recommender/
      matching-policy.md
      scoring-policy.yaml

    skill-registry/
      schema.yaml
      examples.yaml

    lexicon/
      default-user-lexicon.yaml
      schema.yaml

    output-contract/
      promptgate-result.schema.json
      answer-contract.md

  adapters/
    claude/
      CLAUDE.md
      skills/
        promptgate/SKILL.md
      hooks/
        README.md
        user-prompt-submit.example.py

    codex/
      AGENTS.md
      skills/
        promptgate/SKILL.md
      hooks/
        README.md
        user-prompt-submit.example.py

  evals/
    refinement-cases.yaml
    candidate-vs-requirement-cases.yaml
    skill-handoff-cases.yaml
    clarification-cases.yaml
    risk-policy-cases.yaml

  scripts/
    validate-evals.py

  docs/
    architecture.md
    quickstart.md
    configuration.md
    compatibility.md
    contributing.md
    adr/
      0001-core-first-thin-adapters.md
```

`core/` is the source of truth. Adapters translate the core policy into each agent environment, but they do not own separate behavior.

## 4. Core Behavior

PromptGate receives a raw user prompt and produces a refined prompt plus metadata.

The core behavior is:

```text
Raw user prompt
  -> refine intent
  -> separate context
  -> detect explicit skill mention
  -> match registered external skills
  -> apply risk policy
  -> hand off or return refined prompt
```

Prompt refinement follows these rules:

1. Fix the user's main goal first.
2. Separate background from the current request.
3. Treat solution ideas as candidates, not requirements.
4. Preserve exclusions such as "no code" or "direction only."
5. Infer reasonable output preferences from user phrasing.
6. Ask no question if the request can be refined safely.
7. Ask exactly one question if a missing decision materially changes the downstream task.
8. Never invent a skill that is not registered.

## 5. Explicit Skill Mention Policy

If the user mentions a specific skill, that skill becomes the handoff target.

```text
Explicit skill mention wins.
```

Flow:

```text
User mentions a skill
  -> PromptGate checks whether it is registered
  -> PromptGate refines the rest of the prompt
  -> PromptGate passes the refined prompt to that skill
  -> no user confirmation is required for low or medium risk skills
```

Exceptions:

- If the skill is not registered, PromptGate returns `skill_not_found` and uses the refined prompt directly.
- If the skill is high risk or destructive, PromptGate does not auto hand off and marks the result as requiring confirmation.

## 6. Skill Registry

PromptGate uses a registry view of available external skills. This registry can be generated from platform skill metadata or maintained as project configuration.

Example:

```yaml
skills:
  - id: example-refactor-skill
    platform_names:
      claude: example-refactor-skill
      codex: example-refactor-skill
    description: Refines and executes scoped refactoring requests.
    aliases:
      - refactor
      - clean up structure
    domains:
      - dev
    task_types:
      - refactor
      - code-quality
    trigger_phrases:
      - clean this up
      - improve structure
    risk_level: medium
    auto_invocable: true
```

Registry fields:

```yaml
id: string
platform_names:
  claude: string | null
  codex: string | null
description: string
aliases: string[]
domains: string[]
task_types: string[]
trigger_phrases: string[]
risk_level: low | medium | high | destructive
auto_invocable: boolean
```

## 7. Matching Model

PromptGate matches the refined prompt against registered skills.

Matching signals:

- Explicit skill mention.
- Domain match.
- Task type match.
- Alias match.
- Trigger phrase match.
- Description similarity.
- Risk and auto-invocation eligibility.

Scoring starts simple and explainable.

```text
confidence =
  explicit mention bonus
+ domain match
+ task type match
+ alias match
+ trigger phrase match
+ description match
- ambiguity penalty
- risk penalty
```

Rules:

1. Explicit skill mention overrides inferred matches.
2. Safety overrides confidence.
3. A non-registered skill must never be invented.
4. If no skill clears the threshold, PromptGate uses the refined prompt directly.

## 8. Handoff Modes

Default mode is `auto`.

```yaml
promptgate:
  mode: auto
  auto_handoff_threshold: 0.78
  max_recommendations: 3
```

Modes:

```text
auto
  Refine the prompt and automatically hand off to the explicit or best matched safe skill.

suggest
  Refine the prompt and show recommended skills without invoking one.

debug
  Refine the prompt and show intent, context separation, matching scores, and handoff rationale.

off
  Refine the prompt only. Do not recommend or hand off to skills.
```

Risk policy:

```yaml
risk_policy:
  low: auto
  medium: auto
  high: suggest
  destructive: require_confirmation
```

The risk policy applies even when the user explicitly mentions a skill.

## 9. PromptGate Result Schema

PromptGate returns one canonical result object.

```ts
type PromptGateResult = {
  original_prompt: string

  refined_prompt: string

  intent: {
    goal: string
    domain: string
    task_type: string
    confidence: number
  }

  context: {
    background: string[]
    constraints: string[]
    exclusions: string[]
    output_preferences: string[]
    solution_candidates: string[]
    assumptions: string[]
  }

  clarification: {
    needed: boolean
    question: string | null
    reason: string | null
  }

  skill_handoff: {
    mode: "auto" | "suggest" | "debug" | "off"
    explicit_skill_mention: string | null
    target_skill: string | null
    target_source: "explicit" | "matched" | "none"
    confidence: number
    status:
      | "auto_handoff"
      | "suggested"
      | "no_match"
      | "skill_not_found"
      | "blocked_by_risk"
      | "disabled"
    reason: string | null
  }

  safety: {
    risk_level: "low" | "medium" | "high" | "destructive"
    requires_confirmation: boolean
    reason: string | null
  }
}
```

`refined_prompt` must be usable as the direct input to the matched external skill.

## 10. Claude Adapter Behavior

The Claude adapter keeps PromptGate thin.

Responsibilities:

- Provide PromptGate rules in `CLAUDE.md`.
- Provide a `promptgate` skill for direct use.
- Read or generate a skill registry from Claude skill metadata where possible.
- Use `UserPromptSubmit` hook context injection where available.
- Pass refined prompts to matched registered skills through Claude's normal skill mechanism.

v0 does not guarantee deterministic slash-command execution in every Claude setup. It provides strong handoff instructions through context injection and direct skill guidance.

## 11. Codex Adapter Behavior

The Codex adapter mirrors the same core policy.

Responsibilities:

- Provide PromptGate rules in `AGENTS.md`.
- Provide a `promptgate` skill for direct use.
- Read or generate a skill registry from Codex skill metadata where possible.
- Use `UserPromptSubmit` hook context injection where available.
- Pass refined prompts to matched registered skills through Codex's normal skill mechanism.

v0 does not require Codex-specific workflow skills. It only needs registered skill metadata and the core PromptGate policy.

## 12. Eval Strategy

PromptGate uses eval fixtures as product contracts.

Eval groups:

```text
refinement-cases
  Tests goal, context, constraints, exclusions, and output preference extraction.

candidate-vs-requirement-cases
  Tests that solution candidates are not promoted into requirements.

skill-handoff-cases
  Tests explicit mention, inferred match, no match, and not-found behavior.

clarification-cases
  Tests when PromptGate should ask one question or proceed without asking.

risk-policy-cases
  Tests high-risk and destructive skill blocking.
```

v0 validation is deterministic:

- YAML schema validation.
- Required field checks.
- Include and exclude checks.
- Handoff status checks.
- Risk policy checks.
- No fake skill checks.

LLM judge based eval can be added later, but it is not required for v0.

## 13. v0 Implementation Boundary

v0 includes:

1. Core prompt refiner spec.
2. Skill registry schema.
3. Handoff policy.
4. Claude and Codex adapter guidance.
5. Eval fixtures.
6. Validation script.
7. Public documentation.

v0 excludes:

1. Bundled workflow skills.
2. Hardcoded external skill names.
3. Complex LLM judge CI.
4. Deterministic skill invocation across all platforms.
5. Package manager distribution.
6. Destructive auto execution.
7. Subagent orchestration.

## 14. Completion Criteria

v0 is complete when:

- A rough prompt can be converted into `PromptGateResult`.
- The refined prompt can be passed directly to a downstream agent or skill.
- Explicit skill mentions win over inferred matches.
- Registered skills are matched without hardcoded workflow names.
- Missing skills are not invented.
- High-risk and destructive skills are not auto-invoked.
- Eval fixtures validate the above behavior.
- Claude and Codex users can apply the same core policy through their adapters.

## 15. Open Decisions for Implementation Planning

These decisions should be resolved in the implementation plan:

1. Whether the first refiner implementation is instruction-only or backed by a script.
2. Whether the skill registry is manually configured first or discovered from local skill folders.
3. Whether adapter files are hand-maintained in v0 or generated from `core/`.
4. Which exact deterministic checks belong in `scripts/validate-evals.py`.
5. How much of the refined metadata should be visible in normal user output.
