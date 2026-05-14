# Quickstart

Install development dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Validate eval fixtures:

```bash
python3 scripts/validate-evals.py
```

Run deterministic runtime evals:

```bash
python3 -m promptgate eval
```

Run PromptGate manually:

```bash
python3 -m promptgate --json "코드말고 방향만 잡아줘"
```

Real provider calls require:

```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export PROMPTGATE_OPENAI_MODEL=gpt-5
```

PromptGate uses the LLM output as a draft. Python guards enforce the final schema, skill registry, risk policy, and mode policy.
