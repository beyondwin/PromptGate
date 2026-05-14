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
