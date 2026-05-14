# Codex Hook Adapter

This directory contains example hook code for injecting PromptGate context with Codex `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic skill invocation in every Codex setup.

Before enabling the hook, run:

```bash
python3 -m promptgate doctor
```

To verify the real provider path as well, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor validates hook readiness. To preview Codex hook installation, run:

```bash
python3 -m promptgate hooks install --adapter codex
```

To apply the PromptGate-owned hook block, run:

```bash
python3 -m promptgate hooks install --adapter codex --apply
```

Review the resulting Codex configuration for your local Codex version before relying on automatic hook consumption.
