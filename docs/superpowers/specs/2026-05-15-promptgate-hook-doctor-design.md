# PromptGate Hook Doctor Design

Date: 2026-05-15
Status: Ready for implementation planning

## 1. Goal

Make the newly wired PromptGate hook runtime easy to enable and verify before a user puts it on the critical prompt-submission path.

The main product need is a local diagnostic command:

```bash
python3 -m promptgate doctor
python3 -m promptgate doctor --json
python3 -m promptgate doctor --provider
```

By default, `doctor` must be deterministic and credential-free. With `--provider`, it may perform a real provider smoke check when `OPENAI_API_KEY` is present.

## 2. Current State

PromptGate already has:

- `promptgate/cli.py`: accepts a raw prompt or the special `eval` command.
- `promptgate/runtime.py`: runs provider completion, repair, schema validation, and guards.
- `promptgate/hook_io.py`: reads `UserPromptSubmit` JSON, handles bypass, calls runtime, and emits hook JSON.
- Claude and Codex example hook wrappers under `adapters/*/hooks/user-prompt-submit.example.py`.
- Documentation for hook smoke commands in `docs/quickstart.md`, `docs/configuration.md`, and `docs/compatibility.md`.

What is missing:

- A single command that verifies local setup.
- Structured diagnostics that can be used by CI or future installers.
- Clear docs that tell a user how to interpret local-only versus provider checks.

## 3. Scope

### In Scope

- Add a new `promptgate/doctor.py` module.
- Add `python3 -m promptgate doctor`, `doctor --json`, and `doctor --provider` CLI support.
- Verify local config, registry, schema, lexicon, hook script compilation, and hook stdin/stdout smoke paths.
- Optionally run a provider smoke check only when `--provider` is passed.
- Document the command in public docs and adapter hook READMEs.
- Add deterministic tests for report generation, provider skip behavior, hook smoke behavior, and CLI routing.

### Out of Scope

- Installing hook files into a user-specific Claude or Codex configuration directory.
- Mutating user config files.
- Requiring a real provider call in default tests or default `doctor` execution.
- Guaranteeing downstream skill invocation.
- Adding a packaging or release workflow.

## 4. Design Decisions

### Decision 1: `doctor` Is a Runtime Module, Not a Script

The diagnostic logic belongs in `promptgate/doctor.py`, not directly in `cli.py` or a standalone script.

This keeps CLI routing small and makes diagnostics independently testable. It also gives future installers or CI jobs a stable Python API.

### Decision 2: Local-Only Is the Default

`python3 -m promptgate doctor` must not require network access, credentials, or a real provider.

Default checks:

- Load config from the current project root.
- Load the configured registry and report skill count.
- Load the result schema and validate a fallback result.
- Load the configured lexicon and report entry count.
- Confirm Claude and Codex hook scripts exist and compile.
- Run hook smoke checks through subprocesses with `OPENAI_API_KEY` removed:
  - Codex `#raw 그대로` input must emit valid JSON with `PromptGate bypass active`.
  - Claude `코드말고 방향만` input must emit valid JSON with `PromptGate runtime unavailable`.

### Decision 3: Provider Smoke Is Explicit

`--provider` enables an optional real runtime check.

Behavior:

- If `OPENAI_API_KEY` is absent, provider check returns `skipped`, not failed.
- If `OPENAI_API_KEY` is present, `doctor` calls `run_promptgate` with a short prompt and validates that the result is schema-valid.
- Provider failures are reported as failed checks with the exception summary.

This makes the default command stable while still supporting real integration confidence when the user asks for it.

### Decision 4: Reports Have Stable Statuses

Each check returns a structured `DoctorCheck`:

```python
@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str  # "ok", "failed", or "skipped"
    summary: str
    details: dict[str, object] | None = None
```

The report uses:

```python
@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        ...
```

`ok` is true when no check has `status == "failed"`. Skipped provider checks do not fail a local-only report.

### Decision 5: Human Output Is Primary, JSON Output Is Stable

Default output is readable:

```text
PromptGate doctor

OK config: loaded promptgate.config.example.yaml
OK registry: 3 skill(s)
OK schema: fallback result validates
OK lexicon: 6 entry(s)
OK codex hook: valid JSON smoke
OK claude hook: valid JSON fallback smoke
SKIP provider: pass --provider and set OPENAI_API_KEY to run a real provider smoke

Result: OK
```

`--json` prints a stable object:

```json
{
  "ok": true,
  "checks": [
    {
      "name": "config",
      "status": "ok",
      "summary": "loaded promptgate.config.example.yaml",
      "details": {}
    }
  ]
}
```

## 5. Module Contract

`promptgate/doctor.py` exports:

```python
from pathlib import Path

@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str
    details: dict[str, object] | None = None


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        ...

    def as_dict(self) -> dict[str, object]:
        ...


def run_doctor(project_root: Path | None = None, provider: bool = False) -> DoctorReport:
    ...


def format_doctor_report(report: DoctorReport, as_json: bool = False) -> str:
    ...
```

Internal helpers can cover individual checks, but callers should use `run_doctor`.

## 6. CLI Contract

`promptgate/cli.py` recognizes `doctor` as a command:

```bash
python3 -m promptgate doctor
python3 -m promptgate doctor --json
python3 -m promptgate doctor --provider
python3 -m promptgate doctor --provider --json
```

Exit codes:

- `0` when `DoctorReport.ok` is true.
- `1` when any check fails.
- argparse errors still use argparse's normal non-zero behavior.

The existing raw prompt and `eval` behavior must keep working.

## 7. Error Handling

Every diagnostic check should catch expected exceptions and turn them into failed checks instead of crashing the whole command.

Examples:

- Config load failure: `failed config`.
- Registry load failure: `failed registry`.
- Missing hook script: `failed codex hook`.
- Hook subprocess exits non-zero: `failed codex hook`.
- Invalid hook JSON: `failed codex hook`.
- Provider failure under `--provider`: `failed provider`.

Unexpected exceptions inside one check should not prevent later independent checks from running.

## 8. Testing Strategy

Default tests stay deterministic and credential-free.

Add or update tests for:

- `DoctorReport.ok` returns false when any check fails.
- JSON report formatting is parseable and stable.
- Local `run_doctor(provider=False)` reports provider as skipped.
- Hook smoke checks produce ok checks in the committed repo.
- CLI `doctor --json` prints structured output.
- CLI `doctor --provider --json` reports provider skipped when `OPENAI_API_KEY` is absent.
- Existing `eval` and raw prompt CLI tests still pass.

Required verification:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
env -u OPENAI_API_KEY python3 -m promptgate doctor --json
python3 -m py_compile promptgate/doctor.py promptgate/cli.py
```

Provider smoke verification is optional and manual:

```bash
python3 -m promptgate doctor --provider
```

## 9. Documentation Updates

Update:

- `docs/quickstart.md`: add `python3 -m promptgate doctor` as the first hook-readiness check.
- `docs/configuration.md`: explain local-only default and optional provider smoke.
- `adapters/claude/hooks/README.md`: tell users to run doctor before enabling the hook.
- `adapters/codex/hooks/README.md`: mirror the same guidance.

Docs must be explicit that `doctor` does not install hooks or mutate user configuration.

## 10. Acceptance Criteria

This work is complete when:

1. `python3 -m promptgate doctor` exits 0 without `OPENAI_API_KEY` in a correctly configured checkout.
2. `python3 -m promptgate doctor --json` emits parseable JSON with `ok: true`.
3. `python3 -m promptgate doctor --provider --json` reports provider as skipped when `OPENAI_API_KEY` is absent.
4. Hook smoke checks verify both bypass and runtime-unavailable paths.
5. Existing `python3 -m promptgate eval` behavior still works.
6. Public docs explain how and when to use doctor.

## 11. Self-Review

- Placeholder scan: no placeholders remain.
- Internal consistency: local-only default, explicit provider mode, and exit-code behavior match across CLI, module, tests, and docs.
- Scope check: this is one focused implementation slice; hook installation remains out of scope.
- Ambiguity check: provider absence is explicitly `skipped`, not failed.
