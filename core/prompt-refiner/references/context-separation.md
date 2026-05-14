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
