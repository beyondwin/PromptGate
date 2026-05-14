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
