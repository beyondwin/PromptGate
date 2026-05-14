# PromptGate Hook Installer Detailed Specification

## Summary

PromptGate already ships Claude and Codex `UserPromptSubmit` example hooks and a `doctor` command that verifies those hooks are locally usable. The missing product step is safe enablement: users need a command that shows where PromptGate would install hook configuration, can apply that configuration when explicitly requested, preserves existing settings, and verifies readiness afterward.

This specification defines a conservative `python3 -m promptgate hooks install` flow. The installer writes only a PromptGate-owned JSON block. It does not attempt to model every host-agent configuration schema or silently overwrite user-managed settings.

## Goals

- Add a first-party CLI path for installing PromptGate hook configuration for Claude Code and Codex.
- Make dry-run the default so users can inspect planned changes before mutation.
- Require an explicit `--apply` flag for any filesystem write.
- Preserve existing JSON settings and merge only PromptGate-owned keys.
- Back up existing target files before changing them.
- Provide structured JSON output suitable for tests, automation, and future UI wrappers.
- Re-run local hook readiness checks after a successful apply unless the user opts out.
- Keep all tests local-only and deterministic.

## Non-Goals

- Do not guarantee a complete, version-specific Claude Code or Codex hook schema.
- Do not edit host-agent settings outside the PromptGate-owned namespace.
- Do not install API keys, edit shell profiles, or manage provider credentials.
- Do not make PromptGate hook results force deterministic slash-command or skill execution.
- Do not remove old PromptGate backups.
- Do not auto-detect arbitrary third-party configuration locations.

## User-Facing CLI

### Commands

```bash
python3 -m promptgate hooks install --adapter codex
python3 -m promptgate hooks install --adapter claude
python3 -m promptgate hooks install --adapter codex --apply
python3 -m promptgate hooks install --adapter claude --target /path/to/settings.json --apply
python3 -m promptgate hooks install --adapter codex --json
python3 -m promptgate hooks install --adapter codex --apply --skip-doctor
```

`hooks install` is the only hook-management command in this iteration.

### Arguments

- `--adapter {codex,claude}` is required.
- `--target PATH` is optional and overrides target discovery.
- `--apply` is optional and enables writes. Without it, the command is a dry run.
- `--json` is optional and prints only the structured installation report.
- `--skip-doctor` is optional and only affects `--apply`. In dry-run mode it should be reported but should not run doctor.

### Exit Codes

- `0`: dry-run succeeded, apply succeeded, or apply was idempotent.
- `1`: installer validation or IO failed.
- `1`: post-install doctor ran and returned failed checks.
- `2`: argparse usage error, including missing or invalid `--adapter`.

### Human Output

Default output should be compact and scan-friendly:

```text
PromptGate hook installer

Mode: dry-run
Adapter: codex
Target: /Users/kws/.codex/config.json
Hook script: /repo/adapters/codex/hooks/user-prompt-submit.example.py
Target exists: no
Parent directory: would create /Users/kws/.codex
Installed: no
Changed: yes
Backup: none
Doctor: not run in dry-run mode

Result: OK
```

Apply mode example:

```text
PromptGate hook installer

Mode: apply
Adapter: claude
Target: /Users/kws/.claude/settings.json
Hook script: /repo/adapters/claude/hooks/user-prompt-submit.example.py
Target exists: yes
Parent directory: exists
Installed: no
Changed: yes
Backup: /Users/kws/.claude/settings.json.promptgate-backup-20260515010203
Doctor: OK

Result: OK
```

Failure output should include a single clear summary:

```text
PromptGate hook installer

Mode: dry-run
Adapter: codex
Target: /tmp/config.json
Error: target JSON must be an object

Result: FAILED
```

## Target Discovery

Target discovery must be deterministic and side-effect free.

### Codex

Priority:

1. `--target PATH`
2. `$CODEX_HOME/config.json` when `CODEX_HOME` is set and non-empty
3. `~/.codex/config.json`

### Claude

Priority:

1. `--target PATH`
2. `$CLAUDE_CONFIG_DIR/settings.json` when `CLAUDE_CONFIG_DIR` is set and non-empty
3. `~/.claude/settings.json`

### Path Expansion

- Expand `~` in `--target`.
- Resolve relative `--target` against the current working directory.
- Store resolved absolute paths in reports.
- Do not require the target path or parent directory to exist during dry-run.

## Hook Script Discovery

The installer must derive hook script paths from the PromptGate project root:

- Codex: `adapters/codex/hooks/user-prompt-submit.example.py`
- Claude: `adapters/claude/hooks/user-prompt-submit.example.py`

The script path in the installed block must be absolute.

If the script file is missing, dry-run and apply both fail. Missing scripts are real blockers and should not produce a misleading installation plan.

## Installed Configuration Contract

The installer owns this JSON block:

```json
{
  "promptgate": {
    "hooks": {
      "UserPromptSubmit": {
        "command": "python3",
        "args": ["/absolute/path/to/adapters/<adapter>/hooks/user-prompt-submit.example.py"]
      }
    }
  }
}
```

`command` is fixed to `python3` for this iteration because the existing docs and hook smoke commands use `python3`.

`args` contains exactly one string: the absolute hook script path.

The block is intentionally namespaced under `promptgate`. It provides a stable PromptGate-owned contract without claiming that the host agent will automatically consume this exact namespace.

## JSON Merge Rules

### Missing Target

If the target file does not exist, the desired output is a new JSON object containing only the installed configuration contract.

### Existing Target Object

If the target file exists and parses as a JSON object:

- Preserve all unrelated top-level keys.
- Preserve unrelated keys under an existing `promptgate` object.
- Preserve unrelated keys under an existing `promptgate.hooks` object.
- Set or replace only `promptgate.hooks.UserPromptSubmit`.

Example input:

```json
{
  "theme": "dark",
  "promptgate": {
    "enabled": true,
    "hooks": {
      "OtherHook": {
        "command": "echo",
        "args": ["ok"]
      }
    }
  }
}
```

Example output:

```json
{
  "theme": "dark",
  "promptgate": {
    "enabled": true,
    "hooks": {
      "OtherHook": {
        "command": "echo",
        "args": ["ok"]
      },
      "UserPromptSubmit": {
        "command": "python3",
        "args": ["/repo/adapters/codex/hooks/user-prompt-submit.example.py"]
      }
    }
  }
}
```

### Existing Non-Object JSON

If the target file parses as an array, string, number, boolean, or null, fail with `target JSON must be an object`.

### Existing Non-Object PromptGate Keys

If `promptgate` exists but is not an object, fail with `promptgate key must be an object`.

If `promptgate.hooks` exists but is not an object, fail with `promptgate.hooks key must be an object`.

These failures avoid destroying user data under keys PromptGate intends to manage.

### Invalid JSON

If parsing fails, fail with `target JSON is invalid: <parser message>`.

Apply mode must not write a backup or target file when JSON parsing fails.

## Dry-Run Behavior

Dry-run is the default.

Dry-run must:

- Resolve adapter metadata.
- Resolve the target path.
- Resolve the absolute hook script path.
- Read and validate the existing target file when present.
- Compute the merged desired document.
- Report whether apply would change the file.
- Report whether parent directory creation would be needed.
- Report whether a backup would be created if apply were run.
- Not create directories.
- Not create, modify, or back up files.
- Not run doctor.

Dry-run should report `changed=false` when the target already contains the exact desired `promptgate.hooks.UserPromptSubmit` block.

## Apply Behavior

Apply mode runs when `--apply` is present.

Apply must:

1. Run the same validation and merge computation as dry-run.
2. Create the parent directory if it does not exist.
3. If `changed=false`, skip backup and write.
4. If `changed=true` and the target exists, copy the existing file to a timestamped backup path.
5. Write the merged JSON document to the target path.
6. Run `run_doctor(project_root=<repo root>)` unless `--skip-doctor` is set.
7. Mark the report failed if doctor returns `ok=false`.

JSON output should be formatted with `ensure_ascii=False`, `indent=2`, and a trailing newline when written to disk.

## Backup Rules

Backup path format:

```text
<target-name>.promptgate-backup-YYYYMMDDHHMMSS
```

Examples:

- `/Users/kws/.codex/config.json.promptgate-backup-20260515010203`
- `/Users/kws/.claude/settings.json.promptgate-backup-20260515010203`

Rules:

- Backups are only created in apply mode.
- Backups are only created when the target exists and the merged output differs from the current target object.
- Backups are not created when the target is already installed.
- Backup contents must exactly match the original target bytes.
- If the computed backup path already exists, append `-1`, `-2`, and so on until an unused path is found.
- If backup creation fails, fail before writing the target.

## Idempotency

The installer is idempotent for the same project root, adapter, and target.

After a successful apply:

```bash
python3 -m promptgate hooks install --adapter codex --target /tmp/config.json --apply
python3 -m promptgate hooks install --adapter codex --target /tmp/config.json --apply
```

The second command should report:

- `installed=true`
- `changed=false`
- no backup path
- no target write
- doctor still runs unless `--skip-doctor` is set

## Report Model

Create a dedicated report object in `promptgate/hooks.py`.

Suggested dataclass fields:

```python
@dataclass(frozen=True)
class HookInstallReport:
    ok: bool
    adapter: str
    mode: str
    target_path: str
    hook_script_path: str
    target_exists: bool
    parent_exists: bool
    parent_created: bool
    installed: bool
    changed: bool
    backup_path: str | None
    doctor_ran: bool
    doctor_ok: bool | None
    error: str | None
```

`mode` is either `dry-run` or `apply`.

`installed=true` means the current or newly written target contains the desired PromptGate hook block.

`changed=true` means apply would write or did write a different JSON document.

`doctor_ok=None` means doctor did not run.

The report should expose `as_dict()` for CLI JSON output.

## Public Module API

Create `promptgate/hooks.py` with these public functions:

```python
def install_hook(
    adapter: str,
    target: Path | None = None,
    apply: bool = False,
    skip_doctor: bool = False,
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] | None = None,
) -> HookInstallReport:
    ...

def format_hook_install_report(report: HookInstallReport, as_json: bool = False) -> str:
    ...
```

Testing hooks:

- `env` allows tests to provide `CODEX_HOME` or `CLAUDE_CONFIG_DIR`.
- `now` allows tests to assert deterministic backup names.
- `project_root` allows tests to point at the repo root explicitly.

The implementation may add private helpers for target resolution, JSON merge, backup path selection, and report construction.

## CLI Integration

Update `promptgate/cli.py` dispatch:

- Existing `doctor` behavior must remain unchanged.
- Existing `eval` behavior must remain unchanged.
- Existing raw prompt behavior must remain unchanged.
- If `active_argv[0] == "hooks"`, dispatch to `_hooks_main(active_argv[1:])`.

`_hooks_main` should support only the `install` subcommand for now.

Suggested parse behavior:

```bash
python3 -m promptgate hooks
```

Returns argparse usage error.

```bash
python3 -m promptgate hooks install
```

Returns argparse usage error because `--adapter` is required.

```bash
python3 -m promptgate hooks install --adapter codex --json
```

Prints the JSON report and exits `0` when report `ok=true`.

The CLI exit code should be `0 if report.ok else 1`.

## Doctor Integration

Post-install doctor should call:

```python
run_doctor(project_root=project_root)
```

Do not pass `provider=True`; installer verification must remain local-only by default.

When doctor fails:

- The target write remains in place.
- The report has `ok=false`, `doctor_ran=true`, `doctor_ok=false`.
- Human output should show `Doctor: FAILED`.
- JSON output should include the doctor failure status. It does not need to embed every doctor check in v1 unless doing so is straightforward.

When `--skip-doctor` is set:

- The report has `doctor_ran=false`, `doctor_ok=None`.
- Human output should show `Doctor: skipped by --skip-doctor`.

Dry-run never runs doctor:

- The report has `doctor_ran=false`, `doctor_ok=None`.
- Human output should show `Doctor: not run in dry-run mode`.

## Error Handling

The module should convert expected installer failures into a failed report rather than raising to the CLI.

Expected failures:

- unknown adapter
- missing hook script
- invalid target JSON
- target JSON not an object
- non-object `promptgate`
- non-object `promptgate.hooks`
- backup creation failure
- parent directory creation failure
- target write failure
- doctor failure

Unexpected programming errors may still raise.

Human output must not include tracebacks for expected failures.

## Formatting Rules

Target JSON should be written using:

```python
json.dumps(data, ensure_ascii=False, indent=2) + "\n"
```

This keeps output readable and stable for tests.

Preserving original whitespace or key order beyond Python's normal dictionary insertion behavior is not required. The merge should preserve existing object insertion order as much as ordinary `json.load` and assignment allow.

## Security And Safety Notes

- The installer writes a command path into local config; it should only point at PromptGate's checked-in adapter hook script.
- The installer must not execute the hook script during install. Doctor is responsible for hook smoke tests.
- The installer must not read or print API keys.
- The installer must not make network calls.
- `--target` can point anywhere the user can write. The command should still apply the same JSON validation, backup, and merge rules.

## Test Plan

### Unit Tests For `promptgate/hooks.py`

Create `tests/test_promptgate_hooks.py`.

Required cases:

1. `test_codex_dry_run_uses_codex_home_without_writing`
   - Create a temp directory.
   - Pass `env={"CODEX_HOME": "<temp>/codex"}`.
   - Run `install_hook("codex", apply=False, project_root=ROOT, env=env)`.
   - Assert target is `<temp>/codex/config.json`.
   - Assert target file does not exist.
   - Assert `changed=true`, `target_exists=false`, `parent_exists=false`, `ok=true`.

2. `test_claude_dry_run_uses_claude_config_dir_without_writing`
   - Pass `env={"CLAUDE_CONFIG_DIR": "<temp>/claude"}`.
   - Assert target is `<temp>/claude/settings.json`.
   - Assert no files are created.

3. `test_apply_creates_missing_target`
   - Use `--target` equivalent via `target=`.
   - Run apply with `skip_doctor=True`.
   - Assert the file exists.
   - Assert JSON contains `promptgate.hooks.UserPromptSubmit`.
   - Assert `changed=true`, `installed=true`, `backup_path=None`.

4. `test_apply_merges_existing_json_and_preserves_unrelated_keys`
   - Seed target with unrelated top-level and nested PromptGate keys.
   - Run apply.
   - Assert unrelated keys remain.
   - Assert `UserPromptSubmit` is set to the desired block.

5. `test_apply_creates_backup_before_modifying_existing_target`
   - Seed target.
   - Inject deterministic `now`.
   - Run apply.
   - Assert backup path matches timestamp.
   - Assert backup bytes match original bytes.

6. `test_apply_is_idempotent_when_hook_block_matches`
   - Apply once.
   - Apply again with the same args.
   - Assert second report `changed=false`, `installed=true`, `backup_path=None`.

7. `test_invalid_json_fails_without_backup_or_write`
   - Seed target with invalid JSON bytes.
   - Run apply.
   - Assert `ok=false`.
   - Assert original bytes remain unchanged.
   - Assert no backup files exist.

8. `test_non_object_promptgate_key_fails_without_write`
   - Seed target with `{"promptgate": false}`.
   - Run apply.
   - Assert `ok=false`.
   - Assert original content remains unchanged.

9. `test_missing_hook_script_fails_in_dry_run`
   - Use a temp project root without adapter files.
   - Run dry-run.
   - Assert `ok=false` and error mentions missing hook script.

10. `test_json_report_contains_stable_fields`
    - Format a report with `as_json=True`.
    - Parse JSON and assert keys include `ok`, `adapter`, `mode`, `target_path`, `hook_script_path`, `changed`, and `error`.

### CLI Tests

Extend `tests/test_promptgate_cli.py`.

Required cases:

1. `test_hooks_install_json_dry_run_outputs_structured_report`
   - Invoke `main(["hooks", "install", "--adapter", "codex", "--target", "<tmp>/config.json", "--json"])`.
   - Capture stdout.
   - Assert exit code `0`.
   - Assert parsed JSON has `adapter="codex"` and `mode="dry-run"`.
   - Assert target file does not exist.

2. `test_hooks_install_apply_writes_target`
   - Invoke `main(["hooks", "install", "--adapter", "claude", "--target", "<tmp>/settings.json", "--apply", "--skip-doctor", "--json"])`.
   - Assert exit code `0`.
   - Assert target file exists.
   - Assert JSON report has `changed=true`.

3. `test_hooks_install_invalid_target_json_returns_failure`
   - Seed invalid JSON.
   - Invoke dry-run with `--json`.
   - Assert exit code `1`.
   - Assert parsed JSON has `ok=false`.

### Regression Tests

Existing tests must continue passing:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
```

Add manual smoke checks after implementation:

```bash
tmpdir=$(mktemp -d)
python3 -m promptgate hooks install --adapter codex --target "$tmpdir/config.json"
test ! -e "$tmpdir/config.json"
python3 -m promptgate hooks install --adapter codex --target "$tmpdir/config.json" --apply --skip-doctor
python3 -m json.tool "$tmpdir/config.json" >/dev/null
```

## Documentation Updates

Update:

- `docs/quickstart.md`
- `docs/configuration.md`
- `adapters/codex/hooks/README.md`
- `adapters/claude/hooks/README.md`

Docs should explain:

- Run `python3 -m promptgate doctor` first.
- Preview install with `python3 -m promptgate hooks install --adapter <adapter>`.
- Apply with `--apply`.
- Use `--target` for non-standard config paths.
- Existing config files are backed up before modification.
- The installed block is PromptGate-owned and may still need host-agent manual review depending on the user's Claude or Codex setup.

## Acceptance Criteria

- `python3 -m promptgate hooks install --adapter codex --json` returns a successful dry-run report without writing files.
- `python3 -m promptgate hooks install --adapter claude --json` returns a successful dry-run report without writing files.
- `--apply --skip-doctor` creates or updates the target JSON file.
- Existing JSON settings are preserved except for `promptgate.hooks.UserPromptSubmit`.
- Existing target files are backed up before modification.
- Re-running apply with the same inputs reports no changes and creates no backup.
- Invalid JSON fails without writing.
- Missing hook scripts fail in dry-run and apply.
- Existing `doctor`, `eval`, and prompt CLI behavior remain unchanged.
- All local tests and eval validation commands pass.

## Implementation Notes

The implementation should stay small and explicit:

- Put installer behavior in `promptgate/hooks.py`.
- Keep `promptgate/cli.py` limited to argument parsing and report printing.
- Use standard-library modules only: `argparse`, `dataclasses`, `datetime`, `json`, `pathlib`, `shutil`, and typing utilities.
- Avoid broad abstractions for future hook commands until another hook command exists.
- Prefer returning failed reports for expected user/input/IO problems so CLI output stays clean.

## Open Questions

None for this iteration. The spec intentionally chooses a conservative PromptGate-owned JSON namespace rather than host-specific schema mutation.
