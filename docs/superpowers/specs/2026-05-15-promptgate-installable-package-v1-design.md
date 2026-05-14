# PromptGate Installable Package v1 Detailed Specification

## Summary

PromptGate currently works well from a source checkout because runtime code can
read files such as `promptgate.config.example.yaml`, `core/`, `evals/`, and
adapter hook scripts by walking paths under the repository root. That is not
enough for an installable tool. A wheel installed into a fresh virtual
environment must run from arbitrary working directories while still finding its
default configuration, schema, skill registry, lexicon, eval fixtures, and hook
scripts.

This specification defines the first private installable PromptGate package:
`promptgate==0.1.0`, distributed as a Python wheel with a `promptgate` console
script. The release target is private installation and local verification, not
public PyPI publishing.

## Goals

- Build a Python wheel from the repository with standard `pyproject.toml`
  metadata.
- Expose `promptgate` as an installed console command.
- Keep `python3 -m promptgate` working from the source checkout.
- Bundle all runtime assets required for local doctor, eval, runtime fallback,
  and hook installer behavior.
- Make `promptgate doctor --json` work outside the source checkout without
  credentials or network access.
- Make `promptgate eval` work outside the source checkout.
- Make `promptgate hooks install --adapter <adapter>` work outside the source
  checkout and install a hook script path that points at bundled package assets.
- Verify the built wheel in a fresh virtual environment, not only through
  editable/source imports.
- Document the private package boundary, local install path, and public release
  blockers.

## Non-Goals

- Do not publish to public PyPI in this iteration.
- Do not add `promptgate init`, `promptgate config validate`, `hooks status`, or
  `hooks uninstall` in this iteration.
- Do not replace the current project config format.
- Do not create a new provider implementation.
- Do not require real OpenAI credentials for default verification.
- Do not guarantee host-native Claude or Codex hook schema compatibility beyond
  the existing PromptGate-owned JSON block.
- Do not change PromptGate's core prompt refinement, registry, risk, or guard
  semantics.

## User-Facing Behavior

### Source Checkout

From the repository root, existing commands continue to work:

```bash
python3 -m promptgate doctor
python3 -m promptgate eval
python3 -m promptgate hooks install --adapter codex --json
python3 scripts/validate-evals.py
```

When running inside a source checkout, PromptGate should prefer source checkout
assets. This keeps development behavior direct: editing `core/`, `evals/`, or
adapter hook files affects local commands immediately.

### Installed Wheel

After building and installing the wheel:

```bash
python3 -m build --wheel
python3 -m pip install dist/promptgate-0.1.0-py3-none-any.whl
```

the installed console command must work from a directory that does not contain a
PromptGate checkout:

```bash
promptgate doctor --json
promptgate eval
promptgate hooks install --adapter codex --target /tmp/config.json --json
promptgate hooks install --adapter codex --target /tmp/config.json --apply --skip-doctor --json
```

The installed hook block must reference the bundled adapter script:

```json
{
  "promptgate": {
    "hooks": {
      "UserPromptSubmit": {
        "command": "python3",
        "args": [
          "/path/to/site-packages/promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py"
        ]
      }
    }
  }
}
```

The exact site-packages path can vary by virtual environment. Tests should assert
that the path exists and contains the expected bundled asset suffix, not that it
matches one hardcoded absolute path.

## Package Metadata

`pyproject.toml` owns packaging metadata.

Required project metadata:

```toml
[project]
name = "promptgate"
version = "0.1.0"
description = "Prompt refinement toolkit for AI agent workflows."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "LicenseRef-Proprietary" }
dependencies = [
  "PyYAML>=6.0.1,<7",
  "jsonschema>=4.23.0,<5",
  "openai>=1.0,<3"
]

[project.scripts]
promptgate = "promptgate.cli:main"
```

The runtime package version must come from `promptgate/version.py`:

```python
__version__ = "0.1.0"
```

`promptgate/__init__.py` exports that value:

```python
from .runtime import run_promptgate
from .version import __version__

__all__ = ["__version__", "run_promptgate"]
```

Version consistency is verified by tests that parse `pyproject.toml` and compare
`project.version` to `promptgate.__version__`.

## Bundled Asset Contract

PromptGate's installed package must include these files:

```text
promptgate/assets/promptgate.config.example.yaml
promptgate/assets/core/output-contract/promptgate-result.schema.json
promptgate/assets/core/skill-registry/examples.yaml
promptgate/assets/core/lexicon/default-user-lexicon.yaml
promptgate/assets/evals/candidate-vs-requirement-cases.yaml
promptgate/assets/evals/clarification-cases.yaml
promptgate/assets/evals/refinement-cases.yaml
promptgate/assets/evals/risk-policy-cases.yaml
promptgate/assets/evals/skill-handoff-cases.yaml
promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py
promptgate/assets/adapters/claude/hooks/user-prompt-submit.example.py
```

These are package assets, not user config files. PromptGate reads them as
defaults. It does not mutate bundled assets.

`pyproject.toml` must include package data patterns for all of these files:

```toml
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

The implementation may copy files into `promptgate/assets/` during development
as ordinary tracked files. A future release process can replace manual copies
with a generator if duplication becomes painful, but v1 should stay simple and
inspectable.

## Resource Resolution

Create `promptgate/resources.py` with this public API:

```python
from pathlib import Path


def source_root() -> Path: ...
def package_asset_root() -> Path: ...
def runtime_root(project_root: Path | None = None) -> Path: ...
```

### `source_root()`

Returns the repository-style parent directory of the installed `promptgate`
package:

```python
Path(__file__).resolve().parents[1]
```

In a source checkout this points to the repository root. In an installed wheel
this points to the site-packages directory or equivalent installation location,
which is not a PromptGate runtime root unless it contains the required source
files.

### `package_asset_root()`

Returns:

```python
Path(__file__).resolve().parent / "assets"
```

This path must exist in installed wheels.

### `runtime_root(project_root=None)`

Resolution order:

1. `project_root` when provided, otherwise `Path.cwd()`.
2. If that path looks like a PromptGate source/runtime root, use it.
3. Else, if `promptgate/assets` looks like a PromptGate runtime root, use it.
4. Else, return the requested path so downstream errors still mention the
   user's requested location.

A path looks like a PromptGate runtime root when it has:

```text
promptgate.config.yaml OR promptgate.config.example.yaml
core/output-contract/promptgate-result.schema.json
```

This deliberately avoids requiring every optional asset for root detection. The
specific readers remain responsible for clear errors when a required file is
missing.

## Config Resolution

`promptgate.config.yaml` remains the user override mechanism.

`load_config(project_root=None)` must:

1. Capture the requested root:

   ```python
   requested_root = project_root or Path.cwd()
   ```

2. Compute:

   ```python
   root = runtime_root(requested_root)
   ```

3. Prefer a user config at:

   ```text
   <requested_root>/promptgate.config.yaml
   ```

4. Fall back to:

   ```text
   <root>/promptgate.config.yaml
   <root>/promptgate.config.example.yaml
   ```

5. Resolve relative paths inside a user config against `requested_root`.
6. Resolve relative paths inside bundled/default config against `root`.

This matters because an installed user can run:

```bash
mkdir my-project
cd my-project
cat > promptgate.config.yaml
```

and relative `skill_registry.registry_path` values should point into
`my-project`, not into site-packages. Conversely, bundled defaults should point
at bundled registry and lexicon files.

## Schema Resolution

`load_result_schema(project_root=None)` must load:

```text
<runtime_root(project_root)>/core/output-contract/promptgate-result.schema.json
```

This preserves source checkout behavior and enables installed-wheel behavior.

The function should continue returning a parsed JSON object. It should not cache
globally in v1; tests and tools may swap working directories and expect fresh
resolution.

## Runtime Resolution

`run_promptgate` must compute:

```python
root = runtime_root(project_root)
```

and pass that root consistently to:

- `load_config(root)`
- `load_result_schema(root)`
- provider prompt construction
- registry loading through the config's resolved `registry_path`
- lexicon loading through the config's resolved `project_lexicon_path`

The existing fake-provider and fallback behavior must not change.

When no `OPENAI_API_KEY` is set and no fake provider is supplied, runtime still
falls back to a schema-valid `PromptGateResult` with a provider error reason.
Packaging must not make this failure mode worse.

## Doctor Resolution

`run_doctor(project_root=None, provider=False)` must compute:

```python
root = runtime_root(project_root)
```

All local checks use that root:

- config load
- registry load
- schema fallback validation
- lexicon load
- codex hook compile
- claude hook compile
- codex hook smoke
- claude hook smoke

Provider checks remain opt-in through `provider=True`.

The doctor smoke checks must run bundled hook scripts in installed mode. The
hook scripts themselves import `promptgate.hook_io` and should work because the
installed package is importable in the same environment as the console command.

## Hook Installer Resolution

`install_hook(..., project_root=None, ...)` must compute:

```python
root = runtime_root(project_root)
```

Hook script discovery remains adapter-relative:

```text
adapters/codex/hooks/user-prompt-submit.example.py
adapters/claude/hooks/user-prompt-submit.example.py
```

Because `root` may be `promptgate/assets`, the same relative contract works for
both source checkouts and installed wheels:

```text
<repo>/adapters/codex/hooks/user-prompt-submit.example.py
<site-packages>/promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py
```

The existing installer safety rules remain unchanged:

- dry-run by default
- explicit `--apply` for writes
- preserve unrelated JSON keys
- back up existing target files before modification
- do not run doctor in dry-run
- do not make network calls
- report expected failures instead of raising to CLI

## Eval Validation Resolution

Move eval validation into `promptgate/eval_validation.py`.

The package module must expose the same API currently used by tests and scripts:

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

`scripts/validate_evals.py` becomes a compatibility wrapper around
`promptgate.eval_validation`, preserving existing imports:

```python
from promptgate.eval_validation import validate_all
```

`promptgate/eval_runner.py` must compute:

```python
root = runtime_root(project_root)
eval_paths = validate_all(root / "evals")
```

This keeps `python3 -m promptgate eval` and installed `promptgate eval`
consistent.

## Wheel Verification

Create `scripts/verify-wheel-install.py`.

The script must:

1. Create a temporary directory.
2. Build a wheel into that temporary directory:

   ```bash
   python3 -m build --wheel --outdir <tmp>/dist
   ```

3. Create a fresh virtual environment with pip.
4. Install the wheel into that virtual environment.
5. Run installed console commands from a working directory that is not the
   source checkout:

   ```bash
   promptgate doctor --json
   promptgate eval
   promptgate hooks install --adapter codex --target <tmp>/work/config.json --json
   promptgate hooks install --adapter codex --target <tmp>/work/config.json --apply --skip-doctor --json
   promptgate hooks install --adapter codex --target <tmp>/work/config.json --apply --skip-doctor --json
   ```

6. Assert:
   - doctor JSON has `ok: true`
   - eval output includes deterministic guard success
   - dry-run does not create the target file
   - apply creates valid JSON
   - installed hook args point into `promptgate/assets/adapters/codex/hooks`
   - second apply reports `changed: false`

The script should remove `OPENAI_API_KEY` from subprocess environments to keep
the smoke deterministic and local-only.

## CI Contract

Create `.github/workflows/ci.yml` that runs:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest
python scripts/validate-evals.py
python -m promptgate eval
env -u OPENAI_API_KEY python -m promptgate doctor
python scripts/verify-wheel-install.py
```

CI uses Python 3.12 initially. Local development currently uses a newer Python,
but the package metadata should require `>=3.11` because the implementation uses
`tomllib` in tests and modern typing syntax in source.

## Documentation Contract

`README.md` must shift from source-only quickstart to private wheel quickstart:

- install dev dependencies
- build wheel
- install wheel
- run `promptgate doctor`
- run `promptgate eval`
- preview hook installation
- explain real provider env vars

`docs/quickstart.md` must include installed-wheel smoke verification:

```bash
python3 scripts/verify-wheel-install.py
```

`docs/configuration.md` must document source checkout resolution versus bundled
package defaults:

- source checkout assets win when running from a checkout
- local `promptgate.config.yaml` in the current working directory overrides
  bundled defaults
- relative paths inside local config resolve against the local config root
- bundled defaults resolve against `promptgate/assets`

`CHANGELOG.md` must record `0.1.0`.

`LICENSE` must block public redistribution until a real public license is chosen.

## Testing Strategy

### Unit Tests

Run:

```bash
python3 -m unittest
```

Important focused suites:

```bash
python3 -m unittest tests.test_promptgate_package
python3 -m unittest tests.test_promptgate_resources
python3 -m unittest tests.test_promptgate_hooks tests.test_promptgate_doctor tests.test_promptgate_runtime
python3 -m unittest tests.test_promptgate_eval_runner tests.test_validate_evals
```

### Local Tooling

Run:

```bash
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate doctor
```

### Wheel Smoke

Run:

```bash
python3 scripts/verify-wheel-install.py
```

### Wheel Contents

Inspect the built wheel with `zipfile` and assert required assets exist:

```text
promptgate/assets/promptgate.config.example.yaml
promptgate/assets/core/output-contract/promptgate-result.schema.json
promptgate/assets/core/skill-registry/examples.yaml
promptgate/assets/core/lexicon/default-user-lexicon.yaml
promptgate/assets/evals/refinement-cases.yaml
promptgate/assets/adapters/codex/hooks/user-prompt-submit.example.py
promptgate/assets/adapters/claude/hooks/user-prompt-submit.example.py
```

## Error Handling

Expected errors remain explicit and local:

- Missing config: `ConfigError`
- Invalid config shape: `ConfigError`
- Missing registry: `RegistryError`
- Invalid eval fixture: `EvalValidationError`
- Missing hook script: failed `HookInstallReport`
- Invalid hook target JSON: failed `HookInstallReport`
- Provider unavailable: schema-valid fallback result, not a crash

Installed mode should not hide missing package assets. If an asset is absent from
the wheel, tests and wheel smoke should fail loudly.

## Security And Safety

- Do not include credentials in package data.
- Do not read `.env` files implicitly.
- Do not run provider checks unless the user passes `doctor --provider`.
- Do not mutate host-agent config without `hooks install --apply`.
- Do not publish publicly while `LICENSE` is proprietary/private.
- Do not copy user config into package assets.

## Public API Impact

Stable public imports after this release:

```python
from promptgate import __version__, run_promptgate
from promptgate.config import load_config
from promptgate.doctor import run_doctor
from promptgate.hooks import install_hook
from promptgate.runtime import run_promptgate
```

New package-internal API:

```python
from promptgate.resources import runtime_root
from promptgate.eval_validation import validate_all
```

`promptgate.resources` is intentionally simple but can be treated as semi-public
because downstream tests and release tooling may use it.

## Rollback Plan

If packaging breaks source checkout behavior:

1. Revert the package resource resolver changes.
2. Keep `pyproject.toml` only if source tests still pass.
3. Remove bundled assets from the wheel smoke until source behavior is restored.

If installed wheel smoke fails but source tests pass:

1. Inspect wheel contents first.
2. Verify package data patterns.
3. Verify `runtime_root()` chooses `promptgate/assets` outside a checkout.
4. Verify hook scripts are executable through `python3 <script>` and import the
   installed `promptgate` package.

## Acceptance Criteria

- `python3 -m build --wheel` creates `promptgate-0.1.0-py3-none-any.whl`.
- A fresh virtual environment can install the wheel.
- The installed `promptgate` console script is available.
- `promptgate doctor --json` succeeds outside the source checkout without
  `OPENAI_API_KEY`.
- `promptgate eval` succeeds outside the source checkout.
- `promptgate hooks install --adapter codex --target <tmp>/config.json --json`
  succeeds without writing the target.
- `promptgate hooks install --adapter codex --target <tmp>/config.json --apply
  --skip-doctor --json` writes valid JSON.
- Re-running the apply command reports `changed: false`.
- Wheel contents include bundled config, schema, registry, lexicon, eval
  fixtures, and hook scripts.
- README and docs explain private wheel installation and installed-package
  defaults.
- CI runs unit tests, eval validation, doctor, and wheel install smoke.
- Public publishing remains blocked until maintainers approve a public license
  and publishing target.

## Deferred Work

These are deliberately excluded so the package release stays focused:

- `promptgate init`
- `promptgate config validate`
- `promptgate hooks status`
- `promptgate hooks uninstall`
- TestPyPI publishing
- public package naming review
- automatic synchronization between source assets and `promptgate/assets`
- host-native Claude/Codex config schema modeling
