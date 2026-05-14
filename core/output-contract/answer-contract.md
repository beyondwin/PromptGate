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
