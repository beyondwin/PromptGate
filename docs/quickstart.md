# Quickstart

Install development dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Validate evals:

```bash
python3 scripts/validate-evals.py
```

Use PromptGate manually:

1. Read `core/prompt-refiner/SKILL.md`.
2. Refine the user's prompt into `PromptGateResult`.
3. If a registered safe skill is explicitly mentioned or confidently matched, pass `refined_prompt` to that skill.
4. If no skill matches, use `refined_prompt` directly.
