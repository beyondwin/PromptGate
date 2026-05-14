import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
