import copy
import json
import unittest

from promptgate.llm import FakeProvider
from promptgate.result import validate_result
from promptgate.runtime import run_promptgate
from tests.test_promptgate_result import VALID_RESULT


class PromptGateRuntimeTest(unittest.TestCase):
    def test_run_promptgate_returns_guarded_valid_result(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["original_prompt"] = "wrong"
        draft["skill_handoff"]["target_skill"] = "invented-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        provider = FakeProvider([json.dumps(draft, ensure_ascii=False)])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["original_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_run_promptgate_repairs_once(self):
        repaired = copy.deepcopy(VALID_RESULT)
        repaired["refined_prompt"] = "수정된 JSON 결과"
        provider = FakeProvider(["not json", json.dumps(repaired, ensure_ascii=False)])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "수정된 JSON 결과")
        validate_result(result)

    def test_run_promptgate_falls_back_when_provider_and_repair_fail(self):
        provider = FakeProvider(["not json", "still not json"])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_run_promptgate_falls_back_on_provider_error(self):
        provider = FakeProvider([])

        result = run_promptgate("정리해줘", provider=provider)

        self.assertEqual(result["refined_prompt"], "정리해줘")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)


class CapturingProvider:
    def __init__(self, response):
        self.response = response
        self.request = None

    def complete_json(self, request):
        self.request = request
        return self.response

    def repair_json(self, request, invalid_output, error):
        self.request = request
        return self.response


class PromptGateRuntimeContextTest(unittest.TestCase):
    def test_runtime_includes_preflight_and_lexicon_in_provider_payload(self):
        draft = copy.deepcopy(VALID_RESULT)
        provider = CapturingProvider(json.dumps(draft, ensure_ascii=False))

        run_promptgate("코드말고 Redis 쓰면 되나", provider=provider)

        payload = json.loads(provider.request.user_prompt)
        self.assertEqual(payload["preflight"]["domain_guess"], "dev")
        self.assertIn("solution_candidate", payload["preflight"]["risk_flags"])
        phrases = [item["phrase"] for item in payload["matched_user_lexicon"]]
        self.assertIn("코드말고", phrases)


if __name__ == "__main__":
    unittest.main()
