from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
from typing import Any, Callable

from .config import PromptGateConfig, load_config
from .lexicon import load_configured_lexicon
from .registry import load_registry
from .result import build_fallback_result, load_result_schema, validate_result


VALID_STATUSES = {"ok", "failed", "skipped"}
HOOK_SCRIPTS = {
    "codex": Path("adapters/codex/hooks/user-prompt-submit.example.py"),
    "claude": Path("adapters/claude/hooks/user-prompt-submit.example.py"),
}


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str
    details: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid doctor check status: {self.status}")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
        }


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        return all(check.status != "failed" for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": [check.as_dict() for check in self.checks],
        }


def run_doctor(project_root: Path | None = None, provider: bool = False) -> DoctorReport:
    root = (project_root or Path.cwd()).resolve()
    checks: list[DoctorCheck] = []

    config, config_check = _run_check_with_value("config", lambda: _check_config(root))
    checks.append(config_check)

    if config is None:
        checks.append(DoctorCheck("registry", "skipped", "config failed"))
        checks.append(_check_schema(root, mode="auto"))
        checks.append(DoctorCheck("lexicon", "skipped", "config failed"))
    else:
        checks.append(_run_check("registry", lambda: _check_registry(config)))
        checks.append(_check_schema(root, mode=config.mode))
        checks.append(_run_check("lexicon", lambda: _check_lexicon(config)))

    for platform, relative_path in HOOK_SCRIPTS.items():
        script = root / relative_path
        checks.append(_check_hook_compile(platform, script))
    checks.append(
        _check_hook_smoke(
            "codex",
            root / HOOK_SCRIPTS["codex"],
            prompt="#raw 그대로",
            expected_context="PromptGate bypass active",
        )
    )
    checks.append(
        _check_hook_smoke(
            "claude",
            root / HOOK_SCRIPTS["claude"],
            prompt="코드말고 방향만",
            expected_context="PromptGate runtime unavailable",
        )
    )

    checks.append(_check_provider_requested(provider))
    return DoctorReport(checks)


def format_doctor_report(report: DoctorReport, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.as_dict(), ensure_ascii=False, indent=2)

    lines = ["PromptGate doctor", ""]
    for check in report.checks:
        lines.append(f"{_status_label(check.status)} {check.name}: {check.summary}")
    lines.append("")
    lines.append(f"Result: {'OK' if report.ok else 'FAILED'}")
    return "\n".join(lines)


def _check_config(root: Path) -> tuple[PromptGateConfig, str, dict[str, object]]:
    config = load_config(root)
    config_path = root / "promptgate.config.yaml"
    if not config_path.exists():
        config_path = root / "promptgate.config.example.yaml"
    return (
        config,
        f"loaded {config_path.name}",
        {
            "mode": config.mode,
            "registry_path": str(config.registry_path),
        },
    )


def _check_registry(config: PromptGateConfig) -> tuple[str, dict[str, object]]:
    registry = load_registry(config.registry_path)
    skills = registry.as_prompt_payload()
    return f"{len(skills)} skill(s)", {"skill_count": len(skills)}


def _check_schema(root: Path, mode: str) -> DoctorCheck:
    try:
        schema = load_result_schema(root)
        fallback = build_fallback_result("doctor smoke", mode=mode, reason="doctor schema check")
        validate_result(fallback, schema)
    except Exception as exc:
        return DoctorCheck("schema", "failed", str(exc), {"exception": exc.__class__.__name__})
    return DoctorCheck("schema", "ok", "fallback result validates")


def _check_lexicon(config: PromptGateConfig) -> tuple[str, dict[str, object]]:
    entries = load_configured_lexicon(config)
    return f"{len(entries)} entry(s)", {"entry_count": len(entries)}


def _check_hook_compile(platform: str, script: Path) -> DoctorCheck:
    name = f"{platform} hook compile"
    if not script.is_file():
        return DoctorCheck(name, "failed", f"missing {script}")
    try:
        py_compile.compile(str(script), doraise=True)
    except py_compile.PyCompileError as exc:
        return DoctorCheck(name, "failed", str(exc), {"path": str(script)})
    return DoctorCheck(name, "ok", f"{script.relative_to(script.parents[3])} compiles")


def _check_hook_smoke(platform: str, script: Path, prompt: str, expected_context: str) -> DoctorCheck:
    name = f"{platform} hook smoke"
    if not script.is_file():
        return DoctorCheck(name, "failed", f"missing {script}")

    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"prompt": prompt}, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=script.parents[3],
            env=env,
            check=False,
        )
    except Exception as exc:
        return DoctorCheck(name, "failed", str(exc), {"exception": exc.__class__.__name__})

    if completed.returncode != 0:
        return DoctorCheck(
            name,
            "failed",
            f"hook exited {completed.returncode}",
            {"stderr": completed.stderr[-500:]},
        )
    if completed.stderr:
        return DoctorCheck(name, "failed", "hook wrote stderr", {"stderr": completed.stderr[-500:]})

    try:
        payload = json.loads(completed.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
    except Exception as exc:
        return DoctorCheck(
            name,
            "failed",
            f"invalid hook JSON: {exc}",
            {"stdout": completed.stdout[-500:]},
        )

    if expected_context not in context:
        return DoctorCheck(
            name,
            "failed",
            f"missing expected context {expected_context!r}",
            {"context": context},
        )
    return DoctorCheck(name, "ok", f"valid JSON contains {expected_context}")


def _check_provider_requested(provider: bool) -> DoctorCheck:
    if not provider:
        return DoctorCheck(
            "provider",
            "skipped",
            "pass --provider and set OPENAI_API_KEY to run a real provider smoke",
        )
    if not os.environ.get("OPENAI_API_KEY"):
        return DoctorCheck("provider", "skipped", "OPENAI_API_KEY is not set")
    return DoctorCheck("provider", "skipped", "provider smoke implementation is added in Task 3")


def _run_check(
    name: str,
    callback: Callable[[], tuple[str, dict[str, object] | None]],
) -> DoctorCheck:
    try:
        summary, details = callback()
    except Exception as exc:
        return DoctorCheck(name, "failed", str(exc), {"exception": exc.__class__.__name__})
    return DoctorCheck(name, "ok", summary, details)


def _run_check_with_value(
    name: str,
    callback: Callable[[], tuple[Any, str, dict[str, object] | None]],
) -> tuple[Any | None, DoctorCheck]:
    try:
        value, summary, details = callback()
    except Exception as exc:
        return None, DoctorCheck(name, "failed", str(exc), {"exception": exc.__class__.__name__})
    return value, DoctorCheck(name, "ok", summary, details)


def _status_label(status: str) -> str:
    if status == "ok":
        return "OK"
    if status == "skipped":
        return "SKIP"
    return "FAIL"
