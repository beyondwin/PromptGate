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

## Hook Smoke Test

The example Claude and Codex hooks read a `UserPromptSubmit` JSON payload from stdin and emit hook JSON on stdout.

Codex example:

```bash
printf '{"prompt":"코드말고 Redis 쓰면 되나"}' | python3 adapters/codex/hooks/user-prompt-submit.example.py
```

Claude example:

```bash
printf '{"prompt":"코드말고 Redis 쓰면 되나"}' | python3 adapters/claude/hooks/user-prompt-submit.example.py
```

If `OPENAI_API_KEY` is not configured, the hooks still emit valid JSON and preserve the original prompt as raw input.

## Hook Readiness Doctor

Before enabling a PromptGate hook in Claude or Codex, run:

```bash
python3 -m promptgate doctor
```

For automation or CI, use JSON output:

```bash
python3 -m promptgate doctor --json
```

The default doctor command is local-only. It validates config, registry, schema, lexicon, hook script compilation, and hook stdin/stdout smoke paths without making a provider call.

To include a real provider smoke check, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor does not install hooks or mutate user configuration.
