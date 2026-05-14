from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil


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
    except (OSError, ValueError) as exc:
        return _report(base, ok=False, error=str(exc))

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
        f"Parent directory: {_parent_summary(report)}",
        f"Installed: {_yes_no(report.installed)}",
        f"Changed: {_yes_no(report.changed)}",
        f"Backup: {report.backup_path or 'none'}",
        f"Doctor: {_doctor_summary(report)}",
    ]
    if report.error:
        lines.append(f"Error: {report.error}")
    lines.extend(["", f"Result: {'OK' if report.ok else 'FAILED'}"])
    return "\n".join(lines)


def _resolve_target(adapter: str, target: Path | None, env: Mapping[str, str]) -> Path:
    if target is not None:
        return _absolute_path(target)
    if adapter == "codex":
        home = env.get("CODEX_HOME") or str(Path.home() / ".codex")
        return _absolute_path(Path(home).expanduser() / "config.json")
    if adapter == "claude":
        home = env.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
        return _absolute_path(Path(home).expanduser() / "settings.json")
    return _absolute_path(Path.home() / ".promptgate-invalid-target.json")


def _resolve_hook_script(root: Path, adapter: str) -> Path:
    relative = HOOK_RELATIVE_PATHS.get(adapter, Path("missing-hook-script.py"))
    return (root / relative).resolve()


def _absolute_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


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


def _report(base: dict[str, object], ok: bool, error: str | None, **updates: object) -> HookInstallReport:
    data = dict(base)
    data.update(updates)
    data["ok"] = ok
    data["error"] = error
    return HookInstallReport(**data)


def _parent_summary(report: HookInstallReport) -> str:
    if report.parent_exists:
        return "exists"
    if report.parent_created:
        return f"created {Path(report.target_path).parent}"
    return f"would create {Path(report.target_path).parent}"


def _doctor_summary(report: HookInstallReport) -> str:
    if report.mode == "dry-run":
        return "not run in dry-run mode"
    if not report.doctor_ran:
        return "skipped by --skip-doctor"
    if report.doctor_ok:
        return "OK"
    return "FAILED"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
