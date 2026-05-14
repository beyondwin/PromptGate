# PromptGate Architecture

PromptGate has three layers:

1. `core/`: platform-neutral refinement, matching, registry, and output contracts.
2. `adapters/`: Claude and Codex guidance that consumes the core policy.
3. `evals/`: deterministic fixtures that define expected behavior.

The core is the source of truth. Adapters must stay thin and must not introduce separate PromptGate behavior.
