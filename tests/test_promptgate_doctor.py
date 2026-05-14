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
