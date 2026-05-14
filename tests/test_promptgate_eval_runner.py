import unittest
from pathlib import Path

from promptgate.eval_runner import run_eval_suite


class PromptGateEvalRunnerTest(unittest.TestCase):
    def test_run_eval_suite_validates_existing_fixtures(self):
        report = run_eval_suite(Path.cwd())

        self.assertIn("Validated 5 eval file(s).", report)
        self.assertIn("Deterministic runtime guard checks passed.", report)


if __name__ == "__main__":
    unittest.main()
