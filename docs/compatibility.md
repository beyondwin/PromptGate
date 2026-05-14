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

## Runtime Boundary

The Python runtime can produce a final `PromptGateResult`, but v0 still does not guarantee deterministic downstream skill invocation in every Claude or Codex setup.

Adapters may call the runtime from hook scripts and inject either `PromptGateResult` or `refined_prompt` into context. They must not add separate matching, risk, or refinement policy outside the shared core.
