import io
import json
import unittest

from promptgate.hook_io import (
    build_hook_output,
    extract_prompt,
    format_additional_context,
    run_user_prompt_submit_hook,
)
from tests.test_promptgate_result import VALID_RESULT


class PromptGateHookIOTest(unittest.TestCase):
    def test_extract_prompt_accepts_prompt_key(self):
        self.assertEqual(extract_prompt({"prompt": "정리좀"}), "정리좀")

    def test_extract_prompt_accepts_message_key(self):
        self.assertEqual(extract_prompt({"message": "정리좀"}), "정리좀")

    def test_build_hook_output_uses_user_prompt_submit_shape(self):
        output = build_hook_output("context")

        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"],
            "UserPromptSubmit",
        )
        self.assertEqual(
            output["hookSpecificOutput"]["additionalContext"],
            "context",
        )

    def test_format_additional_context_contains_refined_prompt(self):
        context = format_additional_context(VALID_RESULT)

        self.assertIn("PromptGate runtime result", context)
        self.assertIn("문장을 자연스럽게 정리해줘.", context)
        self.assertIn("no_match", context)

    def test_bypass_prompt_does_not_call_runner(self):
        def runner(*args, **kwargs):
            raise AssertionError("runner should not be called")

        stdin = io.StringIO(json.dumps({"prompt": "#raw 그대로"}))
        stdout = io.StringIO()

        exit_code = run_user_prompt_submit_hook(stdin, stdout, runner=runner)

        self.assertEqual(exit_code, 0)
        parsed = json.loads(stdout.getvalue())
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate bypass active", context)

    def test_runtime_failure_still_emits_valid_json(self):
        def runner(*args, **kwargs):
            raise RuntimeError("provider missing")

        stdin = io.StringIO(json.dumps({"prompt": "코드말고 방향만"}))
        stdout = io.StringIO()

        exit_code = run_user_prompt_submit_hook(stdin, stdout, runner=runner)

        self.assertEqual(exit_code, 0)
        parsed = json.loads(stdout.getvalue())
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("provider missing", context)


if __name__ == "__main__":
    unittest.main()
