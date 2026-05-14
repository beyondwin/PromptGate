# Configuration

PromptGate configuration lives in `promptgate.config.yaml`.

Start from:

```text
promptgate.config.example.yaml
```

## Modes

- `auto`: refine and hand off to safe matched skills.
- `suggest`: refine and show skill recommendations.
- `debug`: show full PromptGate metadata.
- `off`: refine only, no handoff.

## Risk Policy

Low and medium risk skills can be handed off automatically. High-risk and destructive skills require confirmation or suggestion mode.

## Runtime Provider

PromptGate's runtime is provider-neutral internally. The first real provider uses an OpenAI-compatible Responses API adapter.

Environment variables:

```bash
OPENAI_API_KEY=sk-your-openai-api-key
PROMPTGATE_OPENAI_MODEL=gpt-5
```

Default tests do not call a real provider. They use fake provider responses and Python guard checks.
