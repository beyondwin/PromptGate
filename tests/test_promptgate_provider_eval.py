import json
import tempfile
import unittest
from pathlib import Path

from promptgate.llm import FakeProvider, PromptGateRequest
from promptgate.provider_eval import (
    ProviderEvalOptions,
    build_case_registry,
    format_provider_eval_report,
    run_provider_eval,
    write_provider_eval_report,
)
from tests.test_promptgate_result import VALID_RESULT


class RaisingProvider:
    def complete_json(self, request: PromptGateRequest) -> str:
        raise RuntimeError("provider exploded")

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        raise RuntimeError("repair unavailable")


def write_fixture(tempdir: str, body: str) -> Path:
    path = Path(tempdir) / "cases.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class PromptGateProviderEvalTest(unittest.TestCase):
    def test_runs_cases_with_fake_provider_and_scores_passes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: simple_pass
    input: "정리좀"
    expected:
      status: no_match
      refined_prompt_includes:
        - "문장을"
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["passed"], 1)
        self.assertEqual(report.totals["failed"], 0)
        self.assertEqual(report.totals["error"], 0)
        self.assertEqual(report.cases[0].status, "passed")

    def test_records_field_mismatch_without_stopping(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: mismatch
    input: "정리좀"
    expected:
      status: auto_handoff
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["failed"], 1)
        self.assertEqual(report.cases[0].failures[0]["field"], "status")

    def test_provider_error_is_recorded_and_execution_continues(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: first_error
    input: "정리좀"
    expected:
      status: no_match
""",
            )

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=RaisingProvider(),
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["error"], 1)
        self.assertEqual(report.cases[0].status, "error")
        self.assertIn("provider exploded", report.cases[0].error)

    def test_case_id_and_limit_filters_cases(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: keep
    input: "정리좀"
    expected:
      status: no_match
  - id: skip
    input: "다른 것"
    expected:
      status: no_match
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), case_ids=["keep"], limit=1, yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual([case.case_id for case in report.cases], ["keep"])

    def test_case_local_registry_can_drive_explicit_skill_guard(self):
        registry = build_case_registry(
            [
                {
                    "id": "case-skill",
                    "risk_level": "low",
                    "auto_invocable": True,
                }
            ]
        )

        self.assertTrue(registry.has("case-skill"))
        self.assertEqual(registry.get("case-skill").description, "Eval fixture skill case-skill.")

    def test_formats_and_writes_report_json(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: simple_pass
    input: "정리좀"
    expected:
      status: no_match
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])
            report_path = Path(tempdir) / "report.json"

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )
            write_provider_eval_report(report, report_path)
            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertIn("Provider eval: 1 cases, 1 passed, 0 failed, 0 error", format_provider_eval_report(report))
        self.assertEqual(payload["totals"]["passed"], 1)
        self.assertEqual(payload["cases"][0]["case_id"], "simple_pass")


if __name__ == "__main__":
    unittest.main()
