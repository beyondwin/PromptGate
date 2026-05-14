# PromptGate Hook Installer Design

## Goal

Add a safe CLI enablement flow for installing PromptGate's example `UserPromptSubmit` hooks into Claude Code or Codex configuration.

The installer should make the next step after `python3 -m promptgate doctor` explicit: show exactly what would change by default, only mutate files when requested, preserve existing user configuration, and re-run readiness checks after installation.

## Non-Goals

- Do not guarantee every Claude Code or Codex release-specific config shape.
- Do not silently overwrite user-managed configuration.
- Do not install provider credentials or edit shell profiles.
- Do not turn PromptGate's advisory hook output into deterministic skill execution.

## CLI Shape

Add a `hooks install` command under the existing `python3 -m promptgate` entrypoint:

```bash
python3 -m promptgate hooks install --adapter codex
python3 -m promptgate hooks install --adapter claude
python3 -m promptgate hooks install --adapter codex --apply
python3 -m promptgate hooks install --adapter claude --target /path/to/settings.json --apply
```

The command is dry-run by default. `--apply` is required for filesystem mutation.

Options:

- `--adapter {codex,claude}` selects the hook adapter.
- `--target PATH` overrides the inferred settings file path.
- `--apply` writes changes.
- `--json` prints a structured installation report.
- `--skip-doctor` skips the post-install readiness check when `--apply` is set.

## Target Discovery

Target resolution should be conservative and deterministic:

- Codex default: `$CODEX_HOME/config.json` when `CODEX_HOME` is set, otherwise `~/.codex/config.json`.
- Claude default: `$CLAUDE_CONFIG_DIR/settings.json` when set, otherwise `~/.claude/settings.json`.
- `--target` always wins.

If the parent directory does not exist, the dry-run report should say it would create it. Apply mode may create the parent directory.

## Configuration Model

The installer manages a small PromptGate-owned JSON block:

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

This block is intentionally namespaced. It avoids making assumptions about complete host-agent hook schemas while still giving users and follow-up automation a stable place to inspect.

When the target file already contains JSON object data, merge only the `promptgate.hooks.UserPromptSubmit` key. Preserve unrelated keys. If the target file is missing, create a JSON object with the block above. If the target file exists but is not a JSON object, fail with a clear message and do not write.

## Safety Behavior

Apply mode must create a timestamped backup before changing an existing target file:

```text
settings.json.promptgate-backup-YYYYMMDDHHMMSS
```

If the target already has the exact desired PromptGate hook block, apply mode should report `changed=false` and skip backup creation.

The installer should report planned operations in all modes:

- adapter
- target path
- hook script path
- whether the target exists
- whether parent directory creation is needed
- whether the hook block is already installed
- backup path when a backup would be or was created
- doctor result when post-install doctor runs

## Runtime Boundaries

Implement installer logic in a dedicated module, not inside `promptgate/cli.py`.

Suggested module responsibilities:

- `promptgate/hooks.py`
  - adapter metadata
  - target path resolution
  - JSON merge and validation
  - dry-run/apply report dataclasses
  - optional post-install doctor execution

`promptgate/cli.py` should only parse arguments, call the module, format output, and choose an exit code.

## Error Handling

Return a non-zero CLI exit code when:

- adapter is invalid
- target JSON cannot be parsed
- target JSON is not an object
- hook script is missing
- apply mode cannot write the target or backup
- post-install doctor runs and fails

Dry-run should still fail for invalid target JSON and missing hook script, because those are real blockers.

## Testing

Use TDD with focused unit tests:

- dry-run reports a Codex target without writing files
- dry-run reports a Claude target without writing files
- apply creates a missing target file with the PromptGate block
- apply merges into an existing JSON object and preserves unrelated keys
- apply creates a backup before modifying an existing file
- apply is idempotent when the desired block already exists
- invalid JSON fails without modifying the file
- CLI routes `hooks install` and supports JSON output

Keep tests local-only. Do not depend on real Claude or Codex installations.

## Documentation

Update quickstart and adapter READMEs to replace "doctor does not install hooks" with the new safe install flow. Keep the docs explicit that host-agent integration details can still require manual review.
