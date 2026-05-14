# ADR 0001: Core First, Thin Adapters

Date: 2026-05-14

## Status

Accepted

## Context

PromptGate must support Claude and Codex without splitting into two separate products. If each adapter owns its own refinement rules, the same user prompt can produce inconsistent behavior across platforms.

## Decision

PromptGate keeps platform-neutral behavior in `core/`. Claude and Codex adapters are thin consumers of that core policy.

Adapters may explain platform-specific installation, skill discovery, and hook behavior, but they must not introduce separate refinement or matching rules.

## Consequences

- Eval fixtures apply to the shared core contract.
- Adapter drift is easier to detect.
- v0 can support both Claude and Codex without building deterministic invocation for every platform.
- Future generators can be added later without changing the product model.
