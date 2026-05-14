from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="promptgate-wheel-smoke-") as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        build_venv_dir = tmp_path / "build-venv"
        venv_dir = tmp_path / "venv"
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        venv.EnvBuilder(with_pip=True).create(build_venv_dir)
        build_python = _venv_python(build_venv_dir)
        _run([str(build_python), "-m", "pip", "install", "build>=1.2,<2"], cwd=work_dir)
        _run([str(build_python), "-m", "build", "--wheel", "--outdir", str(dist_dir)], cwd=ROOT)
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
