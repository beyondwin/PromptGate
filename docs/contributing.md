# Contributing

PromptGate behavior changes should start with eval fixtures.

## Rules

- Do not add named workflow skills to PromptGate core.
- Do not hardcode downstream skill names.
- Add or update eval cases for behavior changes.
- Keep adapters thin.
- Run `python3 scripts/validate-evals.py` before opening a pull request.

## Adding an Eval

Add a case to the relevant file in `evals/`.

Every case needs:

- `id`
- `input`
- non-empty `expected`

Handoff cases that name a target skill must include that skill in `registered_skills`.
