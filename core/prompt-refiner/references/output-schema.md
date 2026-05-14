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
