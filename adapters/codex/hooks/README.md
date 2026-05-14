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

Doctor validates hook readiness but does not install hooks or mutate Codex configuration. Review and test hook scripts before enabling them.
