# PromptGate Hook Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `python3 -m promptgate hooks install` so users can safely preview or apply PromptGate hook configuration for Codex and Claude.

**Architecture:** Add installer behavior in a new `promptgate/hooks.py` module. Keep CLI changes in `promptgate/cli.py` limited to argument parsing, report formatting, and exit-code selection. Tests drive the module API first, then CLI wiring, then documentation.

**Tech Stack:** Python standard library (`argparse`, `dataclasses`, `datetime`, `json`, `os`, `pathlib`, `shutil`, `tempfile`, `unittest`), existing PromptGate `doctor` module, existing `python3 -m unittest` test runner.

---

## File Structure

- Create: `promptgate/hooks.py`
  - Owns adapter metadata, target resolution, JSON merge, backup selection, dry-run/apply behavior, report formatting, and optional post-install doctor execution.
- Create: `tests/test_promptgate_hooks.py`
  - Covers installer module behavior without invoking real Claude or Codex installs.
- Modify: `promptgate/cli.py`
  - Adds `hooks install` dispatch while preserving existing `doctor`, `eval`, and raw prompt behavior.
- Modify: `tests/test_promptgate_cli.py`
  - Adds CLI routing tests for dry-run, apply, and invalid target JSON.
- Modify: `docs/quickstart.md`
  - Documents the preview/apply install flow after doctor.
- Modify: `docs/configuration.md`
  - Documents target discovery, backups, and the PromptGate-owned JSON block.
- Modify: `adapters/codex/hooks/README.md`
  - Replaces "doctor does not install hooks" with Codex install preview/apply commands.
- Modify: `adapters/claude/hooks/README.md`
  - Replaces "doctor does not install hooks" with Claude install preview/apply commands.

## Task 1: Module Contract, Target Resolution, And Dry-Run

**Files:**
- Create: `tests/test_promptgate_hooks.py`
- Create: `promptgate/hooks.py`

- [ ] **Step 1: Write failing module tests for dry-run and missing hook script**

Create `tests/test_promptgate_hooks.py` with this content:

```python
import json
import tempfile
import unittest
from pathlib import Path

from promptgate.hooks import format_hook_install_report, install_hook


ROOT = Path(__file__).resolve().parents[1]


class PromptGateHookInstallDryRunTest(unittest.TestCase):
    def test_codex_dry_run_uses_codex_home_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex"

            report = install_hook(
                "codex",
                apply=False,
                project_root=ROOT,
                env={"CODEX_HOME": str(codex_home)},
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.adapter, "codex")
            self.assertEqual(report.mode, "dry-run")
            self.assertEqual(Path(report.target_path), codex_home / "config.json")
            self.assertFalse((codex_home / "config.json").exists())
            self.assertFalse(report.target_exists)
            self.assertFalse(report.parent_exists)
            self.assertFalse(report.parent_created)
            self.assertFalse(report.installed)
            self.assertTrue(report.changed)
            self.assertIsNone(report.backup_path)
            self.assertFalse(report.doctor_ran)
            self.assertIsNone(report.doctor_ok)

    def test_claude_dry_run_uses_claude_config_dir_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp) / "claude"

            report = install_hook(
                "claude",
                apply=False,
                project_root=ROOT,
                env={"CLAUDE_CONFIG_DIR": str(claude_dir)},
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.adapter, "claude")
            self.assertEqual(Path(report.target_path), claude_dir / "settings.json")
            self.assertFalse((claude_dir / "settings.json").exists())
            self.assertTrue(report.changed)

    def test_missing_hook_script_fails_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=False,
                project_root=Path(tmp),
                env={},
            )

            self.assertFalse(report.ok)
            self.assertIn("missing hook script", report.error)
            self.assertFalse((Path(tmp) / "config.json").exists())

    def test_json_report_contains_stable_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=False,
                project_root=ROOT,
                env={},
            )

            payload = json.loads(format_hook_install_report(report, as_json=True))

            self.assertEqual(
                {
                    "ok",
                    "adapter",
                    "mode",
                    "target_path",
                    "hook_script_path",
                    "target_exists",
                    "parent_exists",
                    "parent_created",
                    "installed",
                    "changed",
                    "backup_path",
                    "doctor_ran",
                    "doctor_ok",
                    "error",
                },
                set(payload),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
ModuleNotFoundError: No module named 'promptgate.hooks'
```

- [ ] **Step 3: Implement the minimal dry-run module**

Create `promptgate/hooks.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Callable, Mapping


HOOK_RELATIVE_PATHS = {
    "codex": Path("adapters/codex/hooks/user-prompt-submit.example.py"),
    "claude": Path("adapters/claude/hooks/user-prompt-submit.example.py"),
}


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

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "adapter": self.adapter,
            "mode": self.mode,
            "target_path": self.target_path,
            "hook_script_path": self.hook_script_path,
            "target_exists": self.target_exists,
            "parent_exists": self.parent_exists,
            "parent_created": self.parent_created,
            "installed": self.installed,
            "changed": self.changed,
            "backup_path": self.backup_path,
            "doctor_ran": self.doctor_ran,
            "doctor_ok": self.doctor_ok,
            "error": self.error,
        }


def install_hook(
    adapter: str,
    target: Path | None = None,
    apply: bool = False,
    skip_doctor: bool = False,
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] | None = None,
) -> HookInstallReport:
    active_env = dict(os.environ if env is None else env)
    root = (project_root or Path.cwd()).resolve()
    mode = "apply" if apply else "dry-run"

    target_path = _resolve_target(adapter, target, active_env)
    hook_script_path = _resolve_hook_script(root, adapter)
    base = {
        "adapter": adapter,
        "mode": mode,
        "target_path": str(target_path),
        "hook_script_path": str(hook_script_path),
        "target_exists": target_path.is_file(),
        "parent_exists": target_path.parent.is_dir(),
        "parent_created": False,
        "installed": False,
        "changed": False,
        "backup_path": None,
        "doctor_ran": False,
        "doctor_ok": None,
    }

    if adapter not in HOOK_RELATIVE_PATHS:
        return _report(base, ok=False, error=f"unknown adapter: {adapter}")
    if not hook_script_path.is_file():
        return _report(base, ok=False, error=f"missing hook script: {hook_script_path}")

    try:
        current = _load_target(target_path)
        desired_block = _desired_hook_block(hook_script_path)
        desired = _merge_promptgate_hook(current, desired_block)
    except ValueError as exc:
        return _report(base, ok=False, error=str(exc))

    installed = _is_installed(current, desired_block)
    changed = desired != current
    return _report(base, ok=True, installed=installed, changed=changed, error=None)


def format_hook_install_report(report: HookInstallReport, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.as_dict(), ensure_ascii=False, indent=2)

    lines = [
        "PromptGate hook installer",
        "",
        f"Mode: {report.mode}",
        f"Adapter: {report.adapter}",
        f"Target: {report.target_path}",
        f"Hook script: {report.hook_script_path}",
        f"Target exists: {_yes_no(report.target_exists)}",
        f"Parent directory: {'exists' if report.parent_exists else f'would create {Path(report.target_path).parent}'}",
        f"Installed: {_yes_no(report.installed)}",
        f"Changed: {_yes_no(report.changed)}",
        f"Backup: {report.backup_path or 'none'}",
        "Doctor: not run in dry-run mode",
    ]
    if report.error:
        lines.append(f"Error: {report.error}")
    lines.extend(["", f"Result: {'OK' if report.ok else 'FAILED'}"])
    return "\n".join(lines)


def _resolve_target(adapter: str, target: Path | None, env: Mapping[str, str]) -> Path:
    if target is not None:
        return target.expanduser().resolve()
    if adapter == "codex":
        home = env.get("CODEX_HOME") or str(Path.home() / ".codex")
        return (Path(home).expanduser() / "config.json").resolve()
    if adapter == "claude":
        home = env.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
        return (Path(home).expanduser() / "settings.json").resolve()
    return (Path.home() / ".promptgate-invalid-target.json").resolve()


def _resolve_hook_script(root: Path, adapter: str) -> Path:
    relative = HOOK_RELATIVE_PATHS.get(adapter, Path("missing-hook-script.py"))
    return (root / relative).resolve()


def _load_target(target_path: Path) -> dict[str, object]:
    if not target_path.exists():
        return {}
    try:
        loaded = json.loads(target_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"target JSON is invalid: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("target JSON must be an object")
    return loaded


def _desired_hook_block(hook_script_path: Path) -> dict[str, object]:
    return {
        "command": "python3",
        "args": [str(hook_script_path)],
    }


def _merge_promptgate_hook(
    current: dict[str, object],
    desired_block: dict[str, object],
) -> dict[str, object]:
    merged = dict(current)
    promptgate = merged.get("promptgate", {})
    if not isinstance(promptgate, dict):
        raise ValueError("promptgate key must be an object")
    promptgate = dict(promptgate)

    hooks = promptgate.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("promptgate.hooks key must be an object")
    hooks = dict(hooks)

    hooks["UserPromptSubmit"] = desired_block
    promptgate["hooks"] = hooks
    merged["promptgate"] = promptgate
    return merged


def _is_installed(current: dict[str, object], desired_block: dict[str, object]) -> bool:
    promptgate = current.get("promptgate")
    if not isinstance(promptgate, dict):
        return False
    hooks = promptgate.get("hooks")
    if not isinstance(hooks, dict):
        return False
    return hooks.get("UserPromptSubmit") == desired_block


def _report(base: dict[str, object], ok: bool, error: str | None, **updates: object) -> HookInstallReport:
    data = dict(base)
    data.update(updates)
    data["ok"] = ok
    data["error"] = error
    return HookInstallReport(**data)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
```

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
Ran 4 tests

OK
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add promptgate/hooks.py tests/test_promptgate_hooks.py
git commit -m "feat: add hook installer dry-run report"
```

## Task 2: Apply Mode, Merge Rules, Backups, And Idempotency

**Files:**
- Modify: `tests/test_promptgate_hooks.py`
- Modify: `promptgate/hooks.py`

- [ ] **Step 1: Add failing apply/merge/backup/error tests**

Append these test classes to `tests/test_promptgate_hooks.py` before the `if __name__ == "__main__":` block:

```python
from datetime import datetime


class PromptGateHookInstallApplyTest(unittest.TestCase):
    def test_apply_creates_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "config.json"

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(report.ok)
            self.assertTrue(target.exists())
            payload = json.loads(target.read_text(encoding="utf-8"))
            hook = payload["promptgate"]["hooks"]["UserPromptSubmit"]
            self.assertEqual(hook["command"], "python3")
            self.assertEqual(hook["args"], [str(ROOT / "adapters/codex/hooks/user-prompt-submit.example.py")])
            self.assertTrue(report.changed)
            self.assertTrue(report.installed)
            self.assertTrue(report.parent_created)
            self.assertIsNone(report.backup_path)
            self.assertFalse(report.doctor_ran)

    def test_apply_merges_existing_json_and_preserves_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "promptgate": {
                            "enabled": True,
                            "hooks": {
                                "OtherHook": {
                                    "command": "echo",
                                    "args": ["ok"],
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = install_hook(
                "claude",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(report.ok)
            self.assertEqual(payload["theme"], "dark")
            self.assertTrue(payload["promptgate"]["enabled"])
            self.assertEqual(payload["promptgate"]["hooks"]["OtherHook"]["command"], "echo")
            self.assertEqual(
                payload["promptgate"]["hooks"]["UserPromptSubmit"]["args"],
                [str(ROOT / "adapters/claude/hooks/user-prompt-submit.example.py")],
            )

    def test_apply_creates_backup_before_modifying_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            original = b'{"theme":"dark"}\n'
            target.write_bytes(original)

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
                now=lambda: datetime(2026, 5, 15, 1, 2, 3),
            )

            backup = Path(tmp) / "config.json.promptgate-backup-20260515010203"
            self.assertTrue(report.ok)
            self.assertEqual(Path(report.backup_path), backup)
            self.assertEqual(backup.read_bytes(), original)

    def test_apply_is_idempotent_when_hook_block_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"

            first = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )
            second = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            self.assertTrue(second.installed)
            self.assertFalse(second.changed)
            self.assertIsNone(second.backup_path)
            self.assertEqual(list(Path(tmp).glob("*.promptgate-backup-*")), [])

    def test_invalid_json_fails_without_backup_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_bytes(b"{invalid")

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertFalse(report.ok)
            self.assertIn("target JSON is invalid", report.error)
            self.assertEqual(target.read_bytes(), b"{invalid")
            self.assertEqual(list(Path(tmp).glob("*.promptgate-backup-*")), [])

    def test_non_object_promptgate_key_fails_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            original = '{"promptgate": false}\n'
            target.write_text(original, encoding="utf-8")

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertFalse(report.ok)
            self.assertEqual(report.error, "promptgate key must be an object")
            self.assertEqual(target.read_text(encoding="utf-8"), original)
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
FAIL: test_apply_creates_missing_target
```

The first apply test should fail because Task 1 has not written files yet.

- [ ] **Step 3: Implement apply mode and backup behavior**

Update `promptgate/hooks.py`:

1. Add imports:

```python
import shutil
```

2. Replace the end of `install_hook` after the `installed = _is_installed(current, desired_block)` assignment with:

```python
    installed = _is_installed(current, desired_block)
    changed = desired != current

    if not apply:
        return _report(base, ok=True, installed=installed, changed=changed, error=None)

    parent_created = False
    backup_path = None
    try:
        if not target_path.parent.exists():
            target_path.parent.mkdir(parents=True)
            parent_created = True
        if changed and target_path.exists():
            backup_path = _backup_path(target_path, now or datetime.now)
            shutil.copyfile(target_path, backup_path)
        if changed:
            target_path.write_text(
                json.dumps(desired, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except OSError as exc:
        return _report(
            base,
            ok=False,
            installed=installed,
            changed=changed,
            parent_created=parent_created,
            backup_path=str(backup_path) if backup_path is not None else None,
            error=str(exc),
        )

    return _report(
        base,
        ok=True,
        target_exists=target_path.is_file(),
        parent_exists=target_path.parent.is_dir(),
        parent_created=parent_created,
        installed=True,
        changed=changed,
        backup_path=str(backup_path) if backup_path is not None else None,
        doctor_ran=False,
        doctor_ok=None,
        error=None,
    )
```

3. Add this helper before `_report`:

```python
def _backup_path(target_path: Path, now: Callable[[], datetime]) -> Path:
    timestamp = now().strftime("%Y%m%d%H%M%S")
    candidate = target_path.with_name(f"{target_path.name}.promptgate-backup-{timestamp}")
    index = 1
    while candidate.exists():
        candidate = target_path.with_name(
            f"{target_path.name}.promptgate-backup-{timestamp}-{index}"
        )
        index += 1
    return candidate
```

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
Ran 10 tests

OK
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add promptgate/hooks.py tests/test_promptgate_hooks.py
git commit -m "feat: apply PromptGate hook installer changes"
```

## Task 3: Doctor Integration And Human Formatting

**Files:**
- Modify: `tests/test_promptgate_hooks.py`
- Modify: `promptgate/hooks.py`

- [ ] **Step 1: Add failing tests for doctor status and human output**

Append these tests to `PromptGateHookInstallApplyTest`:

```python
    def test_apply_runs_doctor_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.doctor_ran)
            self.assertTrue(report.doctor_ok)

    def test_human_report_describes_apply_skip_doctor(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            output = format_hook_install_report(report)

            self.assertIn("Mode: apply", output)
            self.assertIn("Doctor: skipped by --skip-doctor", output)
            self.assertIn("Result: OK", output)
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
FAIL: test_apply_runs_doctor_by_default
```

The failure should show `doctor_ran` is still false.

- [ ] **Step 3: Implement doctor integration and accurate human formatting**

Update the apply success return in `install_hook` so it computes doctor state before returning:

```python
    doctor_ran = False
    doctor_ok = None
    if not skip_doctor:
        from .doctor import run_doctor

        doctor_ran = True
        doctor_report = run_doctor(project_root=root)
        doctor_ok = doctor_report.ok

    return _report(
        base,
        ok=doctor_ok is not False,
        target_exists=target_path.is_file(),
        parent_exists=target_path.parent.is_dir(),
        parent_created=parent_created,
        installed=True,
        changed=changed,
        backup_path=str(backup_path) if backup_path is not None else None,
        doctor_ran=doctor_ran,
        doctor_ok=doctor_ok,
        error=None if doctor_ok is not False else "post-install doctor failed",
    )
```

Replace the doctor line construction in `format_hook_install_report` with a helper:

```python
        f"Doctor: {_doctor_summary(report)}",
```

Add this helper near `_yes_no`:

```python
def _doctor_summary(report: HookInstallReport) -> str:
    if report.mode == "dry-run":
        return "not run in dry-run mode"
    if not report.doctor_ran:
        return "skipped by --skip-doctor"
    if report.doctor_ok:
        return "OK"
    return "FAILED"
```

- [ ] **Step 4: Run focused tests and full existing tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_hooks
python3 -m unittest tests.test_promptgate_doctor tests.test_promptgate_adapter_hooks
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add promptgate/hooks.py tests/test_promptgate_hooks.py
git commit -m "feat: run doctor after hook installation"
```

## Task 4: CLI Routing

**Files:**
- Modify: `tests/test_promptgate_cli.py`
- Modify: `promptgate/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add imports to `tests/test_promptgate_cli.py`:

```python
import tempfile
from pathlib import Path
```

Append this class before the `if __name__ == "__main__":` block:

```python
class PromptGateCLIHooksInstallTest(unittest.TestCase):
    def test_hooks_install_json_dry_run_outputs_structured_report(self):
        from promptgate.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "hooks",
                        "install",
                        "--adapter",
                        "codex",
                        "--target",
                        str(target),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["adapter"], "codex")
            self.assertEqual(payload["mode"], "dry-run")
            self.assertFalse(target.exists())

    def test_hooks_install_apply_writes_target(self):
        from promptgate.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "hooks",
                        "install",
                        "--adapter",
                        "claude",
                        "--target",
                        str(target),
                        "--apply",
                        "--skip-doctor",
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(target.exists())
            self.assertTrue(payload["changed"])

    def test_hooks_install_invalid_target_json_returns_failure(self):
        from promptgate.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text("{invalid", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "hooks",
                        "install",
                        "--adapter",
                        "codex",
                        "--target",
                        str(target),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertFalse(payload["ok"])
            self.assertIn("target JSON is invalid", payload["error"])
```

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli
```

Expected result:

```text
FAIL: test_hooks_install_json_dry_run_outputs_structured_report
```

The command is still treated as a raw prompt before CLI routing is added.

- [ ] **Step 3: Implement `hooks install` dispatch**

In `promptgate/cli.py`, update `main` near the existing doctor dispatch:

```python
    if active_argv and active_argv[0] == "doctor":
        return _doctor_main(active_argv[1:])
    if active_argv and active_argv[0] == "hooks":
        return _hooks_main(active_argv[1:])
```

Add this function after `_doctor_main`:

```python
def _hooks_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Manage PromptGate hooks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install PromptGate hook configuration.")
    install_parser.add_argument("--adapter", choices=("codex", "claude"), required=True)
    install_parser.add_argument("--target", type=Path)
    install_parser.add_argument("--apply", action="store_true")
    install_parser.add_argument("--json", action="store_true")
    install_parser.add_argument("--skip-doctor", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "install":
        from .hooks import format_hook_install_report, install_hook

        report = install_hook(
            args.adapter,
            target=args.target,
            apply=args.apply,
            skip_doctor=args.skip_doctor,
        )
        print(format_hook_install_report(report, as_json=args.json))
        return 0 if report.ok else 1

    parser.error(f"unsupported hooks command: {args.command}")
    return 2
```

Add `Path` to imports:

```python
from pathlib import Path
```

- [ ] **Step 4: Run CLI tests and regression tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli
python3 -m unittest tests.test_promptgate_hooks
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add promptgate/cli.py tests/test_promptgate_cli.py
git commit -m "feat: expose hook installer CLI"
```

## Task 5: Documentation Updates

**Files:**
- Modify: `docs/quickstart.md`
- Modify: `docs/configuration.md`
- Modify: `adapters/codex/hooks/README.md`
- Modify: `adapters/claude/hooks/README.md`

- [ ] **Step 1: Update quickstart install flow**

In `docs/quickstart.md`, replace the final sentence in "Hook Readiness Doctor":

```markdown
Doctor does not install hooks or mutate user configuration.
```

with:

```markdown
Doctor checks readiness. To preview hook installation for a host adapter, run:

```bash
python3 -m promptgate hooks install --adapter codex
python3 -m promptgate hooks install --adapter claude
```

The installer is dry-run by default. To write the PromptGate-owned hook block, pass `--apply`:

```bash
python3 -m promptgate hooks install --adapter codex --apply
```

Use `--target /path/to/settings.json` for non-standard host-agent config paths. Existing target files are backed up before modification.
```

- [ ] **Step 2: Update configuration docs**

Append this section to `docs/configuration.md`:

```markdown
## Hook Installer

Preview install changes without writing files:

```bash
python3 -m promptgate hooks install --adapter codex
python3 -m promptgate hooks install --adapter claude
```

Apply changes explicitly:

```bash
python3 -m promptgate hooks install --adapter codex --apply
```

Target discovery:

- Codex uses `$CODEX_HOME/config.json`, then `~/.codex/config.json`.
- Claude uses `$CLAUDE_CONFIG_DIR/settings.json`, then `~/.claude/settings.json`.
- `--target PATH` overrides discovery.

The installer writes only `promptgate.hooks.UserPromptSubmit` and preserves unrelated JSON keys. Existing files are backed up as `<target>.promptgate-backup-YYYYMMDDHHMMSS` before modification.
```

- [ ] **Step 3: Update adapter READMEs**

In `adapters/codex/hooks/README.md`, replace the final sentence with:

```markdown
Doctor validates hook readiness. To preview Codex hook installation, run:

```bash
python3 -m promptgate hooks install --adapter codex
```

To apply the PromptGate-owned hook block, run:

```bash
python3 -m promptgate hooks install --adapter codex --apply
```

Review the resulting Codex configuration for your local Codex version before relying on automatic hook consumption.
```

In `adapters/claude/hooks/README.md`, replace the final sentence with:

```markdown
Doctor validates hook readiness. To preview Claude hook installation, run:

```bash
python3 -m promptgate hooks install --adapter claude
```

To apply the PromptGate-owned hook block, run:

```bash
python3 -m promptgate hooks install --adapter claude --apply
```

Review the resulting Claude configuration for your local Claude Code version before relying on automatic hook consumption.
```

- [ ] **Step 4: Run documentation-adjacent smoke commands**

Run:

```bash
python3 -m promptgate hooks install --adapter codex --json
python3 -m promptgate hooks install --adapter claude --json
```

Expected result:

```text
"ok": true
"mode": "dry-run"
```

No files should be created by these dry-run commands.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add docs/quickstart.md docs/configuration.md adapters/codex/hooks/README.md adapters/claude/hooks/README.md
git commit -m "docs: document hook installer flow"
```

## Task 6: Full Verification And Final Commit Check

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run full regression verification**

Run:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
```

Expected result:

```text
python3 -m unittest: OK
scripts/validate-evals.py: validation succeeds
python3 -m promptgate eval: suite passes
doctor: Result: OK
```

- [ ] **Step 2: Run manual installer smoke**

Run:

```bash
tmpdir=$(mktemp -d)
python3 -m promptgate hooks install --adapter codex --target "$tmpdir/config.json"
test ! -e "$tmpdir/config.json"
python3 -m promptgate hooks install --adapter codex --target "$tmpdir/config.json" --apply --skip-doctor
python3 -m json.tool "$tmpdir/config.json" >/dev/null
python3 -m promptgate hooks install --adapter codex --target "$tmpdir/config.json" --apply --skip-doctor --json
```

Expected result:

```text
The dry-run command does not create config.json.
The apply command creates valid JSON.
The second apply JSON report contains "changed": false.
```

- [ ] **Step 3: Inspect the diff**

Run:

```bash
git diff --stat main..HEAD
git diff --check
git status --short --branch
```

Expected result:

```text
git diff --check produces no output.
git status shows a clean worktree after all task commits.
```

- [ ] **Step 4: Final report**

Report:

- branch name
- commits created
- files changed
- verification commands and outcomes
- whether the branch is ready to merge into `main`
