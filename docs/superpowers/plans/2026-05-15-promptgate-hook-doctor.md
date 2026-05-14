# PromptGate Hook Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `python3 -m promptgate doctor` command that verifies PromptGate hook readiness locally, with optional provider smoke checks.

**Architecture:** Add `promptgate/doctor.py` as the diagnostic module with structured report types and independent checks. Keep `promptgate/cli.py` limited to command routing and formatting, and document doctor usage in public docs plus adapter hook READMEs.

**Tech Stack:** Python 3.11+ stdlib `unittest`, `dataclasses`, `json`, `subprocess`, `py_compile`, existing PromptGate config/registry/schema/lexicon/runtime modules.

---

## Source Documents

- Spec: `docs/superpowers/specs/2026-05-15-promptgate-hook-doctor-design.md`
- Runtime integration spec: `docs/superpowers/specs/2026-05-14-promptgate-adapter-runtime-integration-design.md`

## File Structure

- Create `promptgate/doctor.py`: owns diagnostic checks, report model, JSON/human formatting, and optional provider smoke.
- Create `tests/test_promptgate_doctor.py`: unit tests for report behavior, local checks, hook smoke checks, and provider smoke branching.
- Modify `promptgate/cli.py`: route `doctor` to `promptgate.doctor`.
- Modify `tests/test_promptgate_cli.py`: cover `doctor --json` and `doctor --provider --json`.
- Modify `docs/quickstart.md`: present doctor as the first hook-readiness command.
- Modify `docs/configuration.md`: explain local-only default and optional provider smoke.
- Modify `adapters/claude/hooks/README.md`: instruct Claude users to run doctor before enabling hooks.
- Modify `adapters/codex/hooks/README.md`: mirror Codex hook doctor guidance.

## Implementation Contract

- Do not install hooks or mutate user configuration.
- Do not make real provider calls unless `--provider` is explicitly requested and `OPENAI_API_KEY` exists.
- Default `doctor` must exit 0 in a correctly configured checkout without credentials.
- Provider absence under `--provider` is `skipped`, not failed.
- Keep every check isolated so one failed check does not prevent unrelated checks from running.

---

### Task 1: Doctor Report Model and Pure Local Checks

**Files:**
- Create: `promptgate/doctor.py`
- Create: `tests/test_promptgate_doctor.py`

- [ ] **Step 1: Write the failing doctor model and local check tests**

Create `tests/test_promptgate_doctor.py`:

```python
import json
import os
import unittest
from pathlib import Path

from promptgate.doctor import (
    DoctorCheck,
    DoctorReport,
    format_doctor_report,
    run_doctor,
)


ROOT = Path(__file__).resolve().parents[1]


class PromptGateDoctorReportTest(unittest.TestCase):
    def test_report_ok_is_false_when_any_check_failed(self):
        report = DoctorReport(
            [
                DoctorCheck("config", "ok", "loaded"),
                DoctorCheck("registry", "failed", "missing registry"),
            ]
        )

        self.assertFalse(report.ok)

    def test_report_as_dict_is_json_serializable(self):
        report = DoctorReport(
            [
                DoctorCheck("config", "ok", "loaded", {"mode": "auto"}),
                DoctorCheck("provider", "skipped", "not requested"),
            ]
        )

        payload = report.as_dict()
        encoded = json.dumps(payload, ensure_ascii=False)
        decoded = json.loads(encoded)

        self.assertTrue(decoded["ok"])
        self.assertEqual(decoded["checks"][0]["details"]["mode"], "auto")
        self.assertIsNone(decoded["checks"][1]["details"])

    def test_format_doctor_report_json(self):
        report = DoctorReport([DoctorCheck("config", "ok", "loaded")])

        parsed = json.loads(format_doctor_report(report, as_json=True))

        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["checks"][0]["name"], "config")

    def test_format_doctor_report_human(self):
        report = DoctorReport(
            [
                DoctorCheck("config", "ok", "loaded promptgate.config.example.yaml"),
                DoctorCheck("provider", "skipped", "not requested"),
            ]
        )

        output = format_doctor_report(report)

        self.assertIn("PromptGate doctor", output)
        self.assertIn("OK config: loaded promptgate.config.example.yaml", output)
        self.assertIn("SKIP provider: not requested", output)
        self.assertIn("Result: OK", output)


class PromptGateDoctorLocalChecksTest(unittest.TestCase):
    def test_run_doctor_local_checks_without_provider_credentials(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            report = run_doctor(project_root=ROOT, provider=False)
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        by_name = {check.name: check for check in report.checks}

        self.assertTrue(report.ok)
        self.assertEqual(by_name["config"].status, "ok")
        self.assertEqual(by_name["registry"].status, "ok")
        self.assertEqual(by_name["schema"].status, "ok")
        self.assertEqual(by_name["lexicon"].status, "ok")
        self.assertEqual(by_name["provider"].status, "skipped")
        self.assertIn("pass --provider", by_name["provider"].summary)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the doctor tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor -v
```

Expected:

```text
ModuleNotFoundError: No module named 'promptgate.doctor'
```

- [ ] **Step 3: Implement report model and pure local checks**

Create `promptgate/doctor.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable

from .config import PromptGateConfig, load_config
from .lexicon import load_configured_lexicon
from .registry import load_registry
from .result import build_fallback_result, load_result_schema, validate_result


VALID_STATUSES = {"ok", "failed", "skipped"}


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
```

- [ ] **Step 4: Run the doctor tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor -v
```

Expected:

```text
Ran 5 tests

OK
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add promptgate/doctor.py tests/test_promptgate_doctor.py
git commit -m "feat: add PromptGate doctor report checks"
```

---

### Task 2: Hook Compile and Smoke Checks

**Files:**
- Modify: `promptgate/doctor.py`
- Modify: `tests/test_promptgate_doctor.py`

- [ ] **Step 1: Write the failing hook smoke test**

Append this test class to `tests/test_promptgate_doctor.py` before the `if __name__ == "__main__":` block:

```python
class PromptGateDoctorHookChecksTest(unittest.TestCase):
    def test_run_doctor_verifies_hook_smoke_paths(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            report = run_doctor(project_root=ROOT, provider=False)
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        by_name = {check.name: check for check in report.checks}

        self.assertEqual(by_name["codex hook compile"].status, "ok")
        self.assertEqual(by_name["claude hook compile"].status, "ok")
        self.assertEqual(by_name["codex hook smoke"].status, "ok")
        self.assertEqual(by_name["claude hook smoke"].status, "ok")
        self.assertIn("PromptGate bypass active", by_name["codex hook smoke"].summary)
        self.assertIn("PromptGate runtime unavailable", by_name["claude hook smoke"].summary)
```

- [ ] **Step 2: Run the hook smoke test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor.PromptGateDoctorHookChecksTest -v
```

Expected:

```text
KeyError: 'codex hook compile'
```

- [ ] **Step 3: Add hook compile and smoke checks**

Modify `promptgate/doctor.py` imports:

```python
from dataclasses import dataclass
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
from typing import Any, Callable
```

Add these constants after `VALID_STATUSES`:

```python
HOOK_SCRIPTS = {
    "codex": Path("adapters/codex/hooks/user-prompt-submit.example.py"),
    "claude": Path("adapters/claude/hooks/user-prompt-submit.example.py"),
}
```

Replace `run_doctor` with:

```python
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
```

Add these helper functions before `_check_provider_requested`:

```python
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
```

- [ ] **Step 4: Run the doctor hook tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add promptgate/doctor.py tests/test_promptgate_doctor.py
git commit -m "feat: add PromptGate hook doctor smoke checks"
```

---

### Task 3: Optional Provider Smoke

**Files:**
- Modify: `promptgate/doctor.py`
- Modify: `tests/test_promptgate_doctor.py`

- [ ] **Step 1: Write failing provider smoke tests**

Append this test class to `tests/test_promptgate_doctor.py` before the `if __name__ == "__main__":` block:

```python
class PromptGateDoctorProviderCheckTest(unittest.TestCase):
    def test_provider_requested_without_key_is_skipped(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            report = run_doctor(project_root=ROOT, provider=True)
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        by_name = {check.name: check for check in report.checks}

        self.assertTrue(report.ok)
        self.assertEqual(by_name["provider"].status, "skipped")
        self.assertEqual(by_name["provider"].summary, "OPENAI_API_KEY is not set")

    def test_provider_requested_with_key_uses_runtime(self):
        import promptgate.doctor as doctor

        previous_key = os.environ.get("OPENAI_API_KEY")
        previous_runner = doctor.run_promptgate
        calls = []

        def fake_run_promptgate(raw_prompt, project_root=None):
            calls.append((raw_prompt, project_root))
            from tests.test_promptgate_result import VALID_RESULT

            result = dict(VALID_RESULT)
            result["original_prompt"] = raw_prompt
            result["refined_prompt"] = raw_prompt
            return result

        os.environ["OPENAI_API_KEY"] = "sk-test"
        doctor.run_promptgate = fake_run_promptgate
        try:
            report = doctor.run_doctor(project_root=ROOT, provider=True)
        finally:
            doctor.run_promptgate = previous_runner
            if previous_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_key

        by_name = {check.name: check for check in report.checks}

        self.assertEqual(by_name["provider"].status, "ok")
        self.assertEqual(calls[0][0], "정리좀")
        self.assertEqual(calls[0][1], ROOT)
```

- [ ] **Step 2: Run provider tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor.PromptGateDoctorProviderCheckTest -v
```

Expected:

```text
AssertionError: 'skipped' != 'ok'
```

- [ ] **Step 3: Implement optional provider smoke**

Modify `promptgate/doctor.py` imports:

```python
from .result import build_fallback_result, load_result_schema, validate_result
from .runtime import run_promptgate
```

Replace the provider call in `run_doctor`:

```python
    checks.append(_check_provider(root, provider))
    return DoctorReport(checks)
```

Replace `_check_provider_requested` with:

```python
def _check_provider(root: Path, provider: bool) -> DoctorCheck:
    if not provider:
        return DoctorCheck(
            "provider",
            "skipped",
            "pass --provider and set OPENAI_API_KEY to run a real provider smoke",
        )
    if not os.environ.get("OPENAI_API_KEY"):
        return DoctorCheck("provider", "skipped", "OPENAI_API_KEY is not set")

    try:
        schema = load_result_schema(root)
        result = run_promptgate("정리좀", project_root=root)
        validate_result(result, schema)
    except Exception as exc:
        return DoctorCheck(
            "provider",
            "failed",
            str(exc),
            {"exception": exc.__class__.__name__},
        )
    return DoctorCheck("provider", "ok", "provider smoke returned a valid PromptGateResult")
```

- [ ] **Step 4: Run doctor tests and verify they pass**

Run:

```bash
python3 -m unittest tests.test_promptgate_doctor -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add promptgate/doctor.py tests/test_promptgate_doctor.py
git commit -m "feat: add optional PromptGate provider doctor smoke"
```

---

### Task 4: CLI Doctor Command

**Files:**
- Modify: `promptgate/cli.py`
- Modify: `tests/test_promptgate_cli.py`

- [ ] **Step 1: Write failing CLI doctor tests**

Append these imports to `tests/test_promptgate_cli.py`:

```python
import contextlib
import io
import os
```

Append this test class before the `if __name__ == "__main__":` block:

```python
class PromptGateCLIDoctorTest(unittest.TestCase):
    def test_doctor_json_cli_outputs_structured_report(self):
        from promptgate.cli import main

        previous = os.environ.pop("OPENAI_API_KEY", None)
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["doctor", "--json"])
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("config", [check["name"] for check in payload["checks"]])

    def test_doctor_provider_json_skips_provider_without_key(self):
        from promptgate.cli import main

        previous = os.environ.pop("OPENAI_API_KEY", None)
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["doctor", "--provider", "--json"])
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        payload = json.loads(stdout.getvalue())
        by_name = {check["name"]: check for check in payload["checks"]}

        self.assertEqual(exit_code, 0)
        self.assertEqual(by_name["provider"]["status"], "skipped")
        self.assertEqual(by_name["provider"]["summary"], "OPENAI_API_KEY is not set")
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli.PromptGateCLIDoctorTest -v
```

Expected:

```text
SystemExit: 2
```

- [ ] **Step 3: Add doctor routing to CLI**

Replace `promptgate/cli.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .runtime import run_promptgate


def format_result(result: dict[str, Any], as_json: bool, debug: bool) -> str:
    if as_json or debug:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return result["refined_prompt"]


def main(argv: list[str] | None = None) -> int:
    active_argv = list(sys.argv[1:] if argv is None else argv)
    if active_argv and active_argv[0] == "doctor":
        return _doctor_main(active_argv[1:])

    parser = argparse.ArgumentParser(description="Run PromptGate over a raw prompt.")
    parser.add_argument("prompt", nargs="*", help="Raw prompt to refine, or 'eval' to run evals.")
    parser.add_argument("--json", action="store_true", help="Print full PromptGateResult JSON.")
    parser.add_argument("--debug", action="store_true", help="Print full PromptGateResult JSON.")
    args = parser.parse_args(active_argv)

    if args.prompt == ["eval"]:
        from .eval_runner import run_eval_suite

        report = run_eval_suite()
        print(report)
        return 0

    raw_prompt = " ".join(args.prompt).strip()
    if not raw_prompt:
        parser.error("prompt is required")

    result = run_promptgate(raw_prompt)
    print(format_result(result, as_json=args.json, debug=args.debug))
    return 0


def _doctor_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify PromptGate hook readiness.")
    parser.add_argument("--json", action="store_true", help="Print structured doctor report JSON.")
    parser.add_argument("--provider", action="store_true", help="Run an optional real provider smoke check.")
    args = parser.parse_args(argv)

    from .doctor import format_doctor_report, run_doctor

    report = run_doctor(provider=args.provider)
    print(format_doctor_report(report, as_json=args.json))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run CLI tests and full doctor tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli tests.test_promptgate_doctor -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add promptgate/cli.py tests/test_promptgate_cli.py
git commit -m "feat: expose PromptGate doctor CLI"
```

---

### Task 5: Doctor Documentation

**Files:**
- Modify: `docs/quickstart.md`
- Modify: `docs/configuration.md`
- Modify: `adapters/claude/hooks/README.md`
- Modify: `adapters/codex/hooks/README.md`

- [ ] **Step 1: Update quickstart**

Append this section to `docs/quickstart.md` after the existing hook smoke test section:

````markdown

## Hook Readiness Doctor

Before enabling a PromptGate hook in Claude or Codex, run:

```bash
python3 -m promptgate doctor
```

For automation or CI, use JSON output:

```bash
python3 -m promptgate doctor --json
```

The default doctor command is local-only. It validates config, registry, schema, lexicon, hook script compilation, and hook stdin/stdout smoke paths without making a provider call.

To include a real provider smoke check, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor does not install hooks or mutate user configuration.
````

- [ ] **Step 2: Update configuration docs**

Append this section to `docs/configuration.md` after the Lexicon section:

````markdown

## Doctor Checks

`python3 -m promptgate doctor` verifies local PromptGate readiness without credentials or network access. It checks:

- configuration loading
- skill registry loading
- result schema validation
- configured lexicon loading
- Claude and Codex hook script compilation
- hook JSON smoke behavior for bypass and provider-unavailable paths

Provider checks are opt-in:

```bash
python3 -m promptgate doctor --provider
```

When `--provider` is set but `OPENAI_API_KEY` is missing, the provider check is reported as skipped. Missing credentials do not make the local readiness check fail.
````

- [ ] **Step 3: Update Claude hook README**

Replace `adapters/claude/hooks/README.md` with:

```markdown
# Claude Hook Adapter

This directory contains example hook code for injecting PromptGate context with Claude Code `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic slash-command execution in every Claude setup.

Before enabling the hook, run:

```bash
python3 -m promptgate doctor
```

To verify the real provider path as well, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor validates hook readiness but does not install hooks or mutate Claude configuration. Review and test hook scripts before enabling them.
```

- [ ] **Step 4: Update Codex hook README**

Replace `adapters/codex/hooks/README.md` with:

```markdown
# Codex Hook Adapter

This directory contains example hook code for injecting PromptGate context with Codex `UserPromptSubmit`.

v0 hook behavior is advisory. It injects refined prompt and handoff guidance into context; it does not guarantee deterministic skill invocation in every Codex setup.

Before enabling the hook, run:

```bash
python3 -m promptgate doctor
```

To verify the real provider path as well, set `OPENAI_API_KEY` and run:

```bash
python3 -m promptgate doctor --provider
```

Doctor validates hook readiness but does not install hooks or mutate Codex configuration. Review and test hook scripts before enabling them.
```

- [ ] **Step 5: Verify documentation text**

Run:

```bash
rg -n "promptgate doctor|doctor --provider|does not install hooks|does not install|mutate" docs adapters
```

Expected:

```text
Matches in docs/quickstart.md, docs/configuration.md, adapters/claude/hooks/README.md, and adapters/codex/hooks/README.md.
```

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add docs/quickstart.md docs/configuration.md adapters/claude/hooks/README.md adapters/codex/hooks/README.md
git commit -m "docs: document PromptGate doctor checks"
```

---

### Task 6: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run the full unit test suite**

Run:

```bash
python3 -m unittest
```

Expected:

```text
OK
```

- [ ] **Step 2: Validate eval fixtures**

Run:

```bash
python3 scripts/validate-evals.py
```

Expected:

```text
Validated 5 eval file(s).
```

- [ ] **Step 3: Run deterministic runtime evals**

Run:

```bash
python3 -m promptgate eval
```

Expected:

```text
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 4: Run local-only doctor**

Run:

```bash
env -u OPENAI_API_KEY python3 -m promptgate doctor
```

Expected:

```text
PromptGate doctor
```

and:

```text
Result: OK
```

- [ ] **Step 5: Run JSON doctor**

Run:

```bash
env -u OPENAI_API_KEY python3 -m promptgate doctor --json
```

Expected:

```text
"ok": true
```

and provider check status:

```text
"status": "skipped"
```

- [ ] **Step 6: Run provider-requested doctor without credentials**

Run:

```bash
env -u OPENAI_API_KEY python3 -m promptgate doctor --provider --json
```

Expected:

```text
"name": "provider"
"status": "skipped"
"summary": "OPENAI_API_KEY is not set"
```

- [ ] **Step 7: Compile changed Python files**

Run:

```bash
python3 -m py_compile promptgate/doctor.py promptgate/cli.py
```

Expected:

```text
No output and exit code 0.
```

- [ ] **Step 8: Check diff hygiene**

Run:

```bash
git diff --check HEAD~5..HEAD
```

Expected:

```text
No output and exit code 0.
```

- [ ] **Step 9: Check git status**

Run:

```bash
git status --short --branch
```

Expected:

```text
## <branch-name>
```

Only intentional untracked planning/spec files may remain if they pre-existed this implementation run.

## Self-Review

Spec coverage:

- `promptgate/doctor.py` module is covered by Tasks 1-3.
- CLI `doctor`, `--json`, and `--provider` are covered by Task 4.
- Local config, registry, schema, lexicon, hook compile, and hook smoke checks are covered by Tasks 1-2.
- Optional provider smoke is covered by Task 3.
- Documentation updates are covered by Task 5.
- Required verification commands are covered by Task 6.

Placeholder scan:

- The plan contains no incomplete implementation steps.
- Every code-producing task includes concrete test or implementation code.
- Every verification step has a command and expected result.

Type consistency:

- `DoctorCheck.as_dict()` is consumed by `DoctorReport.as_dict()`.
- `format_doctor_report(report, as_json=True)` returns parseable JSON for CLI output.
- `run_doctor(project_root=ROOT, provider=True)` is the tested public API for provider mode.
- CLI routing calls `run_doctor(provider=args.provider)` and returns `0` only when `report.ok` is true.
