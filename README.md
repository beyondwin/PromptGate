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
