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


if __name__ == "__main__":
    unittest.main()
