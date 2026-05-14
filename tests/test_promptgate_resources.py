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

    def test_eval_suite_works_outside_checkout(self):
        from promptgate.eval_runner import run_eval_suite

        with tempfile.TemporaryDirectory() as tmp:
            with temporary_cwd(Path(tmp)):
                report = run_eval_suite()

        self.assertIn("Validated 5 eval file(s).", report)
        self.assertIn("Deterministic runtime guard checks passed.", report)


if __name__ == "__main__":
    unittest.main()
