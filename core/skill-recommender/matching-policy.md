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
