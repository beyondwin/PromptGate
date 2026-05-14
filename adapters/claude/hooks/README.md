# Claude Hook Adapter

This directory contains example hook code for injecting PromptGate context with Claude Code `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic slash-command execution in every Claude setup.

Before enabling the hook, run:

```bash
python3 -m promptgate doctor
```

To verify the real provider path as well, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor validates hook readiness. To preview Claude hook installation, run:

```bash
python3 -m promptgate hooks install --adapter claude
```

To apply the PromptGate-owned hook block, run:

```bash
python3 -m promptgate hooks install --adapter claude --apply
```

Review the resulting Claude configuration for your local Claude Code version before relying on automatic hook consumption.
