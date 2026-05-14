# PromptGate Installable Package v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PromptGate installable as a Python wheel with a `promptgate` console command that works outside the source checkout.

**Architecture:** Add standard Python packaging metadata, move runtime defaults behind a package resource resolver, and verify the built wheel in a fresh virtual environment. The installed CLI must find bundled config, schema, registry, lexicon, eval fixtures, and hook scripts without relying on the current working directory being the repository root.

**Tech Stack:** Python standard library (`argparse`, `importlib.resources`, `json`, `pathlib`, `subprocess`, `tempfile`, `tomllib`, `unittest`, `venv`), `setuptools`, `build`, existing PromptGate modules, existing `python3 -m unittest` test runner.

---

## Source Specification

- `docs/superpowers/specs/2026-05-15-promptgate-installable-package-v1-design.md`

## Release Target

This plan produces a private installable package, not a public open-source release.

- Package name: `promptgate`
- Version: `0.1.0`
- Console command: `promptgate`
- Supported local install flows:
  - `python3 -m build --wheel`
  - `python3 -m pip install dist/promptgate-0.1.0-py3-none-any.whl`
  - `pipx install dist/promptgate-0.1.0-py3-none-any.whl`
- Required installed commands:
  - `promptgate doctor --json`
  - `promptgate hooks install --adapter codex --target <tmp>/config.json --json`
  - `promptgate hooks install --adapter codex --target <tmp>/config.json --apply --skip-doctor --json`
  - `promptgate eval`
- Public PyPI publishing remains blocked until the license and project identity are explicitly approved.

## File Structure

- Create: `pyproject.toml`
  - Owns build backend, package metadata, console script entry point, package data, and dependency declarations.
- Create: `promptgate/version.py`
  - Owns the single Python version constant used by `promptgate.__version__` and package metadata.
- Modify: `promptgate/__init__.py`
  - Exports `__version__` from `promptgate.version`.
- Create: `promptgate/resources.py`
  - Resolves either a user/source checkout root or bundled package assets.
- Create: `promptgate/assets/`
  - Bundles runtime assets required outside a source checkout:
    - `promptgate.config.example.yaml`
    - `core/output-contract/promptgate-result.schema.json`
    - `core/skill-registry/examples.yaml`
    - `core/lexicon/default-user-lexicon.yaml`
    - `evals/*.yaml`
    - `adapters/codex/hooks/user-prompt-submit.example.py`
    - `adapters/claude/hooks/user-prompt-submit.example.py`
- Modify: `promptgate/config.py`
  - Falls back to bundled config and bundled asset root when no project config exists in the current directory.
- Modify: `promptgate/result.py`
  - Loads the result schema from bundled assets when the source checkout schema is absent.
- Modify: `promptgate/runtime.py`
  - Uses the resolved runtime root consistently for config, registry, schema, and lexicon.
- Modify: `promptgate/doctor.py`
  - Runs local checks against the resolved runtime root and bundled hook scripts when outside the repo.
- Modify: `promptgate/hooks.py`
  - Resolves hook scripts from bundled assets when outside the repo.
- Create: `promptgate/eval_validation.py`
  - Moves eval fixture validation into the installable package.
- Modify: `promptgate/eval_runner.py`
  - Imports eval validation from `promptgate.eval_validation` and resolves bundled eval fixtures.
- Modify: `scripts/validate_evals.py`
  - Becomes a thin compatibility wrapper around `promptgate.eval_validation`.
- Modify: `scripts/validate-evals.py`
  - Keeps the existing hyphenated command wrapper working.
- Modify: `tests/test_promptgate_package.py`
  - Covers package metadata, version consistency, and console script metadata.
- Create: `tests/test_promptgate_resources.py`
  - Covers runtime behavior from a directory that is not the repository root.
- Create: `scripts/verify-wheel-install.py`
  - Builds a wheel, installs it in a fresh venv, and runs installed CLI smoke checks.
- Modify: `requirements-dev.txt`
  - Adds `build` for local wheel verification.
- Modify: `README.md`
  - Documents install-from-wheel and private release boundary.
- Modify: `docs/quickstart.md`
  - Adds installed CLI workflow.
- Modify: `docs/configuration.md`
  - Explains project config override versus bundled defaults.
- Create: `CHANGELOG.md`
  - Records `0.1.0` release notes.
- Create: `LICENSE`
  - Uses a private all-rights-reserved license notice until a public license is chosen.
- Create: `.github/workflows/ci.yml`
  - Runs tests, eval validation, wheel build, and installed-wheel smoke.

## Task 1: Package Metadata, Version Source, And Console Script

**Files:**
- Create: `pyproject.toml`
- Create: `promptgate/version.py`
- Modify: `promptgate/__init__.py`
- Modify: `tests/test_promptgate_package.py`
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Write failing package metadata tests**

Replace `tests/test_promptgate_package.py` with:

```python
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptGatePackageTest(unittest.TestCase):
    def test_package_exports_version(self):
        import promptgate

        self.assertEqual(promptgate.__version__, "0.1.0")

    def test_pyproject_metadata_matches_runtime_version(self):
        import promptgate

        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["name"], "promptgate")
        self.assertEqual(pyproject["project"]["version"], promptgate.__version__)
        self.assertEqual(
            pyproject["project"]["scripts"]["promptgate"],
            "promptgate.cli:main",
        )
        self.assertIn("PyYAML>=6.0.1,<7", pyproject["project"]["dependencies"])
        self.assertIn("jsonschema>=4.23.0,<5", pyproject["project"]["dependencies"])
        self.assertIn("openai>=1.0,<3", pyproject["project"]["dependencies"])

    def test_module_entrypoint_still_invokes_cli_help(self):
        completed = subprocess.run(
            [sys.executable, "-m", "promptgate", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Run PromptGate over a raw prompt.", completed.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run package tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_package
```

Expected result:

```text
FileNotFoundError: ... pyproject.toml
```

- [ ] **Step 3: Add package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "promptgate"
version = "0.1.0"
description = "Prompt refinement toolkit for AI agent workflows."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "LicenseRef-Proprietary" }
authors = [
  { name = "PromptGate maintainers" }
]
dependencies = [
  "PyYAML>=6.0.1,<7",
  "jsonschema>=4.23.0,<5",
  "openai>=1.0,<3"
]

[project.scripts]
promptgate = "promptgate.cli:main"

[tool.setuptools]
packages = ["promptgate"]
include-package-data = true

[tool.setuptools.package-data]
promptgate = [
  "assets/promptgate.config.example.yaml",
  "assets/core/output-contract/*.json",
  "assets/core/skill-registry/*.yaml",
  "assets/core/lexicon/*.yaml",
  "assets/evals/*.yaml",
  "assets/adapters/codex/hooks/*.py",
  "assets/adapters/claude/hooks/*.py"
]
```

Create `promptgate/version.py`:

```python
__version__ = "0.1.0"
```

Replace `promptgate/__init__.py` with:

```python
from .runtime import run_promptgate
from .version import __version__

__all__ = ["__version__", "run_promptgate"]
```

Append `build` to `requirements-dev.txt`:

```text
build>=1.2,<2
```

- [ ] **Step 4: Run package tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_package
```

Expected result:

```text
Ran 3 tests

OK
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add pyproject.toml promptgate/version.py promptgate/__init__.py tests/test_promptgate_package.py requirements-dev.txt
git commit -m "build: add PromptGate package metadata"
```

## Task 2: Bundled Runtime Assets And Resource Resolution

**Files:**
- Create: `promptgate/resources.py`
- Create: `promptgate/assets/promptgate.config.example.yaml`
- Create: `promptgate/assets/core/output-contract/promptgate-result.schema.json`
- Create: `promptgate/assets/core/skill-registry/examples.yaml`
- Create: `promptgate/assets/core/lexicon/default-user-lexicon.yaml`
- Create: `promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py`
- Create: `promptgate/assets/adapters/claude/hooks/user-prompt-submit.example.py`
- Modify: `promptgate/config.py`
- Modify: `promptgate/result.py`
- Modify: `promptgate/runtime.py`
- Modify: `promptgate/doctor.py`
- Modify: `promptgate/hooks.py`
- Create: `tests/test_promptgate_resources.py`

- [ ] **Step 1: Write failing resource fallback tests**

Create `tests/test_promptgate_resources.py`:

```python
import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from promptgate.config import load_config
from promptgate.doctor import run_doctor
from promptgate.hooks import install_hook
from promptgate.resources import runtime_root
from promptgate.result import load_result_schema


ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def temporary_cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class PromptGateResourceFallbackTest(unittest.TestCase):
    def test_runtime_root_uses_project_root_when_config_exists(self):
        self.assertEqual(runtime_root(ROOT), ROOT)

    def test_runtime_root_uses_packaged_assets_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with temporary_cwd(Path(tmp)):
                root = runtime_root()

            self.assertNotEqual(root, Path(tmp))
            self.assertTrue((root / "promptgate.config.example.yaml").is_file())
            self.assertTrue((root / "core/output-contract/promptgate-result.schema.json").is_file())

    def test_load_config_works_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with temporary_cwd(Path(tmp)):
                config = load_config()

            self.assertEqual(config.mode, "auto")
            self.assertTrue(config.registry_path.is_file())
            self.assertIn("promptgate/assets", str(config.registry_path))

    def test_load_result_schema_works_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with temporary_cwd(Path(tmp)):
                schema = load_result_schema()

            self.assertEqual(schema["title"], "PromptGateResult")

    def test_hook_installer_uses_packaged_hook_script_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            with temporary_cwd(Path(tmp)):
                report = install_hook("codex", target=target, apply=False, env={})

            self.assertTrue(report.ok)
            self.assertIn("promptgate/assets/adapters/codex/hooks", report.hook_script_path)
            self.assertFalse(target.exists())

    def test_doctor_works_outside_checkout_without_provider(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with temporary_cwd(Path(tmp)):
                    report = run_doctor(provider=False)
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertTrue(report.ok)
        by_name = {check.name: check for check in report.checks}
        self.assertEqual(by_name["config"].status, "ok")
        self.assertEqual(by_name["codex hook smoke"].status, "ok")
        self.assertEqual(by_name["claude hook smoke"].status, "ok")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run resource tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_resources
```

Expected result:

```text
ModuleNotFoundError: No module named 'promptgate.resources'
```

- [ ] **Step 3: Create bundled assets**

Run these copy commands from the repository root:

```bash
mkdir -p promptgate/assets/core/output-contract
mkdir -p promptgate/assets/core/skill-registry
mkdir -p promptgate/assets/core/lexicon
mkdir -p promptgate/assets/adapters/codex/hooks
mkdir -p promptgate/assets/adapters/claude/hooks
cp promptgate.config.example.yaml promptgate/assets/promptgate.config.example.yaml
cp core/output-contract/promptgate-result.schema.json promptgate/assets/core/output-contract/promptgate-result.schema.json
cp core/skill-registry/examples.yaml promptgate/assets/core/skill-registry/examples.yaml
cp core/lexicon/default-user-lexicon.yaml promptgate/assets/core/lexicon/default-user-lexicon.yaml
cp adapters/codex/hooks/user-prompt-submit.example.py promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py
cp adapters/claude/hooks/user-prompt-submit.example.py promptgate/assets/adapters/claude/hooks/user-prompt-submit.example.py
```

- [ ] **Step 4: Add resource resolver**

Create `promptgate/resources.py`:

```python
from __future__ import annotations

from pathlib import Path


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def package_asset_root() -> Path:
    return Path(__file__).resolve().parent / "assets"


def runtime_root(project_root: Path | None = None) -> Path:
    candidate = (project_root or Path.cwd()).resolve()
    if _looks_like_promptgate_root(candidate):
        return candidate
    assets = package_asset_root()
    if _looks_like_promptgate_root(assets):
        return assets
    return candidate


def _looks_like_promptgate_root(path: Path) -> bool:
    return (
        (path / "promptgate.config.yaml").is_file()
        or (path / "promptgate.config.example.yaml").is_file()
    ) and (path / "core/output-contract/promptgate-result.schema.json").is_file()
```

- [ ] **Step 5: Update config loading**

In `promptgate/config.py`, add the import:

```python
from .resources import runtime_root
```

Replace `load_config` with:

```python
def load_config(project_root: Path | None = None) -> PromptGateConfig:
    requested_root = project_root or Path.cwd()
    root = runtime_root(requested_root)
    local_config = requested_root / "promptgate.config.yaml"
    root_local_config = root / "promptgate.config.yaml"
    example_config = root / "promptgate.config.example.yaml"

    if local_config.exists():
        path = local_config
        config_root = requested_root
    elif root_local_config.exists():
        path = root_local_config
        config_root = root
    else:
        path = example_config
        config_root = root

    if not path.exists():
        raise ConfigError(f"PromptGate config not found at {local_config} or {example_config}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("promptgate"), dict):
        raise ConfigError(f"{path}: expected top-level promptgate mapping")

    return PromptGateConfig.from_mapping(payload["promptgate"], project_root=config_root)
```

- [ ] **Step 6: Update schema loading**

In `promptgate/result.py`, add the import:

```python
from .resources import runtime_root
```

Replace `load_result_schema` with:

```python
def load_result_schema(project_root: Path | None = None) -> dict[str, Any]:
    root = runtime_root(project_root)
    schema_path = root / "core/output-contract/promptgate-result.schema.json"
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
```

- [ ] **Step 7: Update runtime root selection**

In `promptgate/runtime.py`, add the import:

```python
from .resources import runtime_root
```

Replace the first line inside `run_promptgate` that computes `root` with:

```python
    root = runtime_root(project_root)
```

- [ ] **Step 8: Update doctor root selection**

In `promptgate/doctor.py`, add the import:

```python
from .resources import runtime_root
```

Replace the first line inside `run_doctor` that computes `root` with:

```python
    root = runtime_root(project_root)
```

- [ ] **Step 9: Update hook installer root selection**

In `promptgate/hooks.py`, add the import:

```python
from .resources import runtime_root
```

Replace the line inside `install_hook` that computes `root` with:

```python
    root = runtime_root(project_root)
```

- [ ] **Step 10: Run resource tests and focused regressions**

Run:

```bash
python3 -m unittest tests.test_promptgate_resources
python3 -m unittest tests.test_promptgate_hooks tests.test_promptgate_doctor tests.test_promptgate_runtime
```

Expected result:

```text
OK
```

- [ ] **Step 11: Commit Task 2**

Run:

```bash
git add promptgate/resources.py promptgate/assets promptgate/config.py promptgate/result.py promptgate/runtime.py promptgate/doctor.py promptgate/hooks.py tests/test_promptgate_resources.py
git commit -m "feat: resolve PromptGate runtime assets from package data"
```

## Task 3: Installable Eval Validation

**Files:**
- Create: `promptgate/eval_validation.py`
- Modify: `promptgate/eval_runner.py`
- Modify: `scripts/validate_evals.py`
- Modify: `scripts/validate-evals.py`
- Create: `promptgate/assets/evals/candidate-vs-requirement-cases.yaml`
- Create: `promptgate/assets/evals/clarification-cases.yaml`
- Create: `promptgate/assets/evals/refinement-cases.yaml`
- Create: `promptgate/assets/evals/risk-policy-cases.yaml`
- Create: `promptgate/assets/evals/skill-handoff-cases.yaml`
- Modify: `tests/test_promptgate_resources.py`

- [ ] **Step 1: Add failing eval fallback test**

Append this test method to `PromptGateResourceFallbackTest` in `tests/test_promptgate_resources.py`:

```python
    def test_eval_suite_works_outside_checkout(self):
        from promptgate.eval_runner import run_eval_suite

        with tempfile.TemporaryDirectory() as tmp:
            with temporary_cwd(Path(tmp)):
                report = run_eval_suite()

        self.assertIn("Validated 5 eval file(s).", report)
        self.assertIn("Deterministic runtime guard checks passed.", report)
```

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_resources.PromptGateResourceFallbackTest.test_eval_suite_works_outside_checkout
```

Expected result:

```text
EvalValidationError: ... evals directory does not exist
```

- [ ] **Step 3: Copy eval fixtures into package assets**

Run:

```bash
mkdir -p promptgate/assets/evals
cp evals/*.yaml promptgate/assets/evals/
```

- [ ] **Step 4: Move eval validation into the package**

Create `promptgate/eval_validation.py` by copying the full current contents of `scripts/validate_evals.py`, then remove only the executable tail:

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

The resulting `promptgate/eval_validation.py` must still define:

```python
EvalValidationError
load_yaml
validate_eval_file
validate_case
validate_registered_skills
validate_expected
validate_all
main
```

- [ ] **Step 5: Turn script module into a compatibility wrapper**

Replace `scripts/validate_evals.py` with:

```python
from promptgate.eval_validation import (
    EvalValidationError,
    load_yaml,
    main,
    validate_all,
    validate_case,
    validate_eval_file,
    validate_expected,
    validate_registered_skills,
)

__all__ = [
    "EvalValidationError",
    "load_yaml",
    "main",
    "validate_all",
    "validate_case",
    "validate_eval_file",
    "validate_expected",
    "validate_registered_skills",
]


if __name__ == "__main__":
    raise SystemExit(main())
```

Ensure `scripts/validate-evals.py` still delegates to the underscore module:

```python
from scripts.validate_evals import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Update eval runner to use package validation and runtime root**

In `promptgate/eval_runner.py`, replace:

```python
from scripts.validate_evals import validate_all
```

with:

```python
from .eval_validation import validate_all
from .resources import runtime_root
```

Replace the first line inside `run_eval_suite` that computes `root` with:

```python
    root = runtime_root(project_root)
```

- [ ] **Step 7: Run eval tests and resource tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_runner tests.test_validate_evals tests.test_promptgate_resources
python3 scripts/validate-evals.py
python3 -m promptgate eval
```

Expected result:

```text
OK
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add promptgate/eval_validation.py promptgate/eval_runner.py scripts/validate_evals.py scripts/validate-evals.py promptgate/assets/evals tests/test_promptgate_resources.py
git commit -m "feat: package PromptGate eval fixtures and validation"
```

## Task 4: Wheel Build And Fresh-Venv Install Smoke

**Files:**
- Create: `scripts/verify-wheel-install.py`
- Modify: `tests/test_promptgate_package.py`

- [ ] **Step 1: Add a package-data coverage test**

Append this method to `PromptGatePackageTest` in `tests/test_promptgate_package.py`:

```python
    def test_pyproject_package_data_includes_runtime_assets(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package_data = pyproject["tool"]["setuptools"]["package-data"]["promptgate"]

        self.assertIn("assets/promptgate.config.example.yaml", package_data)
        self.assertIn("assets/core/output-contract/*.json", package_data)
        self.assertIn("assets/core/skill-registry/*.yaml", package_data)
        self.assertIn("assets/core/lexicon/*.yaml", package_data)
        self.assertIn("assets/evals/*.yaml", package_data)
        self.assertIn("assets/adapters/codex/hooks/*.py", package_data)
        self.assertIn("assets/adapters/claude/hooks/*.py", package_data)
```

- [ ] **Step 2: Run package tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_package
```

Expected result:

```text
OK
```

- [ ] **Step 3: Add installed-wheel smoke script**

Create `scripts/verify-wheel-install.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="promptgate-wheel-smoke-") as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        venv_dir = tmp_path / "venv"
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)], cwd=ROOT)
        wheels = sorted(dist_dir.glob("promptgate-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one promptgate wheel, found {wheels}")

        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = _venv_python(venv_dir)
        promptgate = _venv_promptgate(venv_dir)

        _run([str(python), "-m", "pip", "install", str(wheels[0])], cwd=work_dir)

        doctor = _json_command([str(promptgate), "doctor", "--json"], cwd=work_dir)
        if not doctor["ok"]:
            raise RuntimeError(f"installed doctor failed: {doctor}")

        eval_result = _run([str(promptgate), "eval"], cwd=work_dir)
        if "Deterministic runtime guard checks passed." not in eval_result.stdout:
            raise RuntimeError(eval_result.stdout)

        target = work_dir / "codex-config.json"
        dry_run = _json_command(
            [
                str(promptgate),
                "hooks",
                "install",
                "--adapter",
                "codex",
                "--target",
                str(target),
                "--json",
            ],
            cwd=work_dir,
        )
        if not dry_run["ok"] or dry_run["mode"] != "dry-run" or target.exists():
            raise RuntimeError(f"unexpected dry-run report: {dry_run}")

        apply = _json_command(
            [
                str(promptgate),
                "hooks",
                "install",
                "--adapter",
                "codex",
                "--target",
                str(target),
                "--apply",
                "--skip-doctor",
                "--json",
            ],
            cwd=work_dir,
        )
        if not apply["ok"] or not target.exists():
            raise RuntimeError(f"unexpected apply report: {apply}")

        installed = json.loads(target.read_text(encoding="utf-8"))
        args = installed["promptgate"]["hooks"]["UserPromptSubmit"]["args"]
        if len(args) != 1 or "promptgate/assets/adapters/codex/hooks" not in args[0]:
            raise RuntimeError(f"unexpected installed hook args: {args}")

        second_apply = _json_command(
            [
                str(promptgate),
                "hooks",
                "install",
                "--adapter",
                "codex",
                "--target",
                str(target),
                "--apply",
                "--skip-doctor",
                "--json",
            ],
            cwd=work_dir,
        )
        if second_apply["changed"]:
            raise RuntimeError(f"second apply was not idempotent: {second_apply}")

    print("Installed wheel smoke passed.")
    return 0


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def _json_command(command: list[str], cwd: Path) -> dict[str, object]:
    completed = _run(command, cwd=cwd)
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"expected JSON object from {' '.join(command)}")
    return parsed


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/python.exe"
    return venv_dir / "bin/python"


def _venv_promptgate(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/promptgate.exe"
    return venv_dir / "bin/promptgate"


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run wheel smoke**

Run:

```bash
python3 scripts/verify-wheel-install.py
```

Expected result:

```text
Installed wheel smoke passed.
```

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add scripts/verify-wheel-install.py tests/test_promptgate_package.py
git commit -m "test: verify PromptGate wheel installation"
```

## Task 5: Installed CLI Documentation And Release Files

**Files:**
- Modify: `README.md`
- Modify: `docs/quickstart.md`
- Modify: `docs/configuration.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`

- [ ] **Step 1: Update README install section**

In `README.md`, replace the current quickstart dependency section with this installed-package flow:

```markdown
## Quickstart

Build and install the private wheel:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m build --wheel
python3 -m pip install dist/promptgate-0.1.0-py3-none-any.whl
```

Verify the installed CLI:

```bash
promptgate doctor
promptgate eval
```

Preview hook installation:

```bash
promptgate hooks install --adapter codex
promptgate hooks install --adapter claude
```

Run PromptGate over a raw prompt:

```bash
promptgate --json "Redis 쓰면 되나 세션이랑 캐시랑 같이 쓰고 싶은데"
```

Real provider calls require:

```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export PROMPTGATE_OPENAI_MODEL=gpt-5
```
```

- [ ] **Step 2: Add package verification to quickstart**

Append this section to `docs/quickstart.md`:

```markdown
## Installed Package Smoke

Before distributing a wheel, run:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/verify-wheel-install.py
```

The smoke script builds a wheel, installs it into a fresh virtual environment, and verifies `promptgate doctor --json`, `promptgate eval`, and hook install dry-run/apply behavior outside the source checkout.
```

- [ ] **Step 3: Document config resolution**

Append this section to `docs/configuration.md`:

```markdown
## Installed Package Defaults

When PromptGate runs inside a source checkout, config and core assets are read from that checkout. When PromptGate runs from an installed wheel outside a checkout, it uses bundled package assets:

- `promptgate/assets/promptgate.config.example.yaml`
- `promptgate/assets/core/output-contract/promptgate-result.schema.json`
- `promptgate/assets/core/skill-registry/examples.yaml`
- `promptgate/assets/core/lexicon/default-user-lexicon.yaml`

A local `promptgate.config.yaml` in the current working directory overrides bundled defaults. Relative paths inside that local config are resolved against the directory containing the local config.
```

- [ ] **Step 4: Add changelog**

Create `CHANGELOG.md`:

```markdown
# Changelog

## 0.1.0 - 2026-05-15

- Added PromptGate runtime, deterministic eval validation, and local doctor checks.
- Added Claude and Codex `UserPromptSubmit` example hook scripts.
- Added `promptgate hooks install` for dry-run and apply flows.
- Added private wheel packaging with bundled runtime assets.
- Added installed-wheel smoke verification.
```

- [ ] **Step 5: Add private license notice**

Create `LICENSE`:

```text
Copyright (c) 2026 PromptGate maintainers.

All rights reserved.

This repository and package are private unless a separate written license grants
additional rights. Do not redistribute, sublicense, or publish this software to a
public package index until the maintainers choose an explicit public license.
```

- [ ] **Step 6: Run documentation and package smoke**

Run:

```bash
python3 -m unittest tests.test_promptgate_package tests.test_promptgate_resources
python3 scripts/verify-wheel-install.py
```

Expected result:

```text
OK
Installed wheel smoke passed.
```

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add README.md docs/quickstart.md docs/configuration.md CHANGELOG.md LICENSE
git commit -m "docs: document private PromptGate package release"
```

## Task 6: CI For Package Release Checks

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Add CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: python -m pip install -r requirements-dev.txt
      - name: Run unit tests
        run: python -m unittest
      - name: Validate eval fixtures
        run: python scripts/validate-evals.py
      - name: Run deterministic eval suite
        run: python -m promptgate eval
      - name: Run local doctor
        run: env -u OPENAI_API_KEY python -m promptgate doctor
      - name: Verify installed wheel
        run: python scripts/verify-wheel-install.py
```

- [ ] **Step 2: Run equivalent CI commands locally**

Run:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
python3 scripts/verify-wheel-install.py
```

Expected result:

```text
python3 -m unittest: OK
scripts/validate-evals.py: validation succeeds
python3 -m promptgate eval: deterministic checks pass
doctor: Result: OK
verify-wheel-install.py: Installed wheel smoke passed.
```

- [ ] **Step 3: Commit Task 6**

Run:

```bash
git add .github/workflows/ci.yml
git commit -m "ci: verify PromptGate package release"
```

## Task 7: Full Verification And Release Readiness Report

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run full verification**

Run:

```bash
python3 -m unittest
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
python3 scripts/verify-wheel-install.py
git diff --check
git status --short --branch
```

Expected result:

```text
All tests pass.
Eval validation succeeds.
PromptGate eval succeeds.
Doctor result is OK.
Installed wheel smoke passes.
git diff --check prints no output.
git status shows a clean worktree after all task commits.
```

- [ ] **Step 2: Inspect package contents**

Run:

```bash
tmpdir=$(mktemp -d)
python3 -m build --wheel --outdir "$tmpdir/dist"
python3 - <<'PY' "$tmpdir"/dist/promptgate-0.1.0-py3-none-any.whl
import sys
import zipfile

wheel = sys.argv[1]
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())

required = {
    "promptgate/assets/promptgate.config.example.yaml",
    "promptgate/assets/core/output-contract/promptgate-result.schema.json",
    "promptgate/assets/core/skill-registry/examples.yaml",
    "promptgate/assets/core/lexicon/default-user-lexicon.yaml",
    "promptgate/assets/evals/refinement-cases.yaml",
    "promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py",
    "promptgate/assets/adapters/claude/hooks/user-prompt-submit.example.py",
}

missing = sorted(required - names)
if missing:
    raise SystemExit(f"missing wheel assets: {missing}")
print("wheel assets present")
PY
```

Expected result:

```text
wheel assets present
```

- [ ] **Step 3: Final report**

Report:

- branch name
- commits created
- files changed
- verification commands and outcomes
- wheel path produced by the final build
- whether the package is ready for private installation
- explicit note that public package publishing remains blocked by license/project identity approval

## Acceptance Criteria

- `python3 -m build --wheel` creates `promptgate-0.1.0-py3-none-any.whl`.
- A fresh virtual environment can install the wheel.
- The installed `promptgate` console script is available.
- `promptgate doctor --json` succeeds outside the source checkout without `OPENAI_API_KEY`.
- `promptgate eval` succeeds outside the source checkout.
- `promptgate hooks install --adapter codex --target <tmp>/config.json --json` succeeds without writing the target.
- `promptgate hooks install --adapter codex --target <tmp>/config.json --apply --skip-doctor --json` writes valid JSON.
- Re-running the apply command reports `changed=false`.
- Wheel contents include bundled config, schema, registry, lexicon, eval fixtures, and hook scripts.
- README and docs explain private wheel installation and installed-package defaults.
- CI runs unit tests, eval validation, doctor, and wheel install smoke.
- Public publishing remains blocked until maintainers approve a public license and publishing target.

## Self-Review Notes

- Spec coverage: package metadata, bundled assets, installed CLI, evals, doctor, hook installer, docs, and CI are covered by Tasks 1-7.
- Placeholder scan: the plan contains no placeholder markers, no open-ended validation instructions, and no unspecified error-handling steps.
- Type consistency: `runtime_root(project_root: Path | None = None) -> Path` is used consistently by config, result, runtime, doctor, hooks, and eval runner.
- Scope control: `init`, `config validate`, `hooks status`, and `hooks uninstall` are excluded from this package plan. They should be implemented after the installable wheel is stable.
