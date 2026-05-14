import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from promptgate.cli import format_result
from tests.test_promptgate_result import VALID_RESULT


class PromptGateCLITest(unittest.TestCase):
    def test_format_result_json_outputs_full_json(self):
        output = format_result(VALID_RESULT, as_json=True, debug=False)
        parsed = json.loads(output)

        self.assertEqual(parsed["original_prompt"], "정리좀")

    def test_format_result_debug_outputs_full_json(self):
        output = format_result(VALID_RESULT, as_json=False, debug=True)
        parsed = json.loads(output)

        self.assertEqual(parsed["skill_handoff"]["status"], "no_match")

    def test_format_result_default_outputs_refined_prompt(self):
        output = format_result(VALID_RESULT, as_json=False, debug=False)

        self.assertEqual(output, "문장을 자연스럽게 정리해줘.")

    def test_eval_cli_remains_deterministic(self):
        from promptgate.cli import main

        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(["eval"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Deterministic runtime guard checks passed.", stdout.getvalue())

    def test_provider_eval_missing_key_returns_usage_error(self):
        from promptgate.cli import main

        previous = os.environ.pop("OPENAI_API_KEY", None)
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["eval", "--provider", "--yes", "--limit", "1"])
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertEqual(exit_code, 2)
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())

    def test_provider_eval_non_tty_without_yes_returns_usage_error(self):
        from promptgate.cli import main

        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "fake-key"
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["eval", "--provider", "--limit", "1"])
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertEqual(exit_code, 2)
        self.assertIn("--yes", stderr.getvalue())


class PromptGateCLIProviderEvalTest(unittest.TestCase):
    def test_provider_eval_cli_can_use_injected_provider_for_tests(self):
        from promptgate.cli import main
        from promptgate.llm import FakeProvider

        provider_result = dict(VALID_RESULT)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                ["eval", "--provider", "--yes", "--case-id", "no_question_when_direction_clear"],
                provider_factory=lambda: FakeProvider([json.dumps(provider_result, ensure_ascii=False)]),
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Provider eval: 1 cases", stdout.getvalue())
        self.assertIn("Failures:", stdout.getvalue())

    def test_provider_eval_cli_writes_report_json(self):
        from promptgate.cli import main
        from promptgate.llm import FakeProvider

        provider_result = dict(VALID_RESULT)
        with tempfile.TemporaryDirectory() as tempdir:
            report_path = Path(tempdir) / "report.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "eval",
                        "--provider",
                        "--yes",
                        "--case-id",
                        "natural_rewrite",
                        "--report-json",
                        str(report_path),
                    ],
                    provider_factory=lambda: FakeProvider([json.dumps(provider_result, ensure_ascii=False)]),
                )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["metadata"]["case_count"], 1)
        self.assertEqual(payload["cases"][0]["case_id"], "natural_rewrite")


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


if __name__ == "__main__":
    unittest.main()
