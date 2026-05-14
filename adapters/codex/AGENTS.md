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
