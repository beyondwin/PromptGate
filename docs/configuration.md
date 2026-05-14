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
