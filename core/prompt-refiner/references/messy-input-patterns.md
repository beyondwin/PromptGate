# Messy Input Patterns

PromptGate should handle rough prompts without criticizing the user.

## Common Patterns

| User Phrase | Interpretation |
|---|---|
| 정리좀 | Keep the meaning, make it clearer and more usable. |
| 방향만 | Prefer strategy, structure, and decision criteria over implementation details. |
| 코드말고 | Exclude code. Answer with architecture, reasoning, or direction only. |
| 별론데 | Identify problems and suggest better direction. |
| 이거 맞아? | Separate correct parts, incorrect parts, and uncertain assumptions. |
| 너무 AI같지 않게 | Remove generic marketing tone, exaggeration, and empty phrases. |
| 구조가 안잡힘 | Clarify goal, actors, scope, and output shape before downstream work. |

## Candidate Language

Phrases like "Redis 쓰면 되나", "이 방법이면 되나", and "X로 하면 어때" usually introduce a candidate solution, not a requirement.

Correct handling:

- Put the candidate in `solution_candidates`.
- Put the underlying need in `goal` or `constraints`.
- Do not force the downstream skill to use the candidate.
