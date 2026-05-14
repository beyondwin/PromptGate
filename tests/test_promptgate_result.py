import copy
import json
import unittest
from pathlib import Path

from promptgate.result import (
    ResultValidationError,
    build_fallback_result,
    load_result_schema,
    parse_json_document,
    provider_schema,
    validate_result,
)


VALID_RESULT = {
    "original_prompt": "정리좀",
    "refined_prompt": "문장을 자연스럽게 정리해줘.",
    "intent": {
        "goal": "문장을 자연스럽게 정리한다.",
        "domain": "writing",
        "task_type": "rewrite",
        "confidence": 0.9,
    },
    "context": {
        "background": [],
        "constraints": [],
        "exclusions": [],
        "output_preferences": ["natural"],
        "solution_candidates": [],
        "assumptions": [],
    },
    "clarification": {
        "needed": False,
        "question": None,
        "reason": None,
    },
    "skill_handoff": {
        "mode": "auto",
        "explicit_skill_mention": None,
        "target_skill": None,
        "target_source": "none",
        "confidence": 0,
        "status": "no_match",
        "reason": None,
    },
    "safety": {
        "risk_level": "low",
        "requires_confirmation": False,
        "reason": None,
    },
}


class PromptGateResultTest(unittest.TestCase):
    def test_parse_json_document_accepts_plain_json(self):
        parsed = parse_json_document(json.dumps(VALID_RESULT, ensure_ascii=False))

        self.assertEqual(parsed["original_prompt"], "정리좀")

    def test_parse_json_document_accepts_fenced_json(self):
        parsed = parse_json_document("```json\n" + json.dumps(VALID_RESULT, ensure_ascii=False) + "\n```")

        self.assertEqual(parsed["intent"]["domain"], "writing")

    def test_validate_result_accepts_valid_result(self):
        validate_result(VALID_RESULT)

    def test_validate_result_rejects_missing_required_field(self):
        invalid = copy.deepcopy(VALID_RESULT)
        invalid.pop("safety")

        with self.assertRaises(ResultValidationError):
            validate_result(invalid)

    def test_build_fallback_result_is_schema_valid(self):
        result = build_fallback_result("raw prompt", mode="suggest", reason="provider failed")

        self.assertEqual(result["original_prompt"], "raw prompt")
        self.assertEqual(result["refined_prompt"], "raw prompt")
        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        validate_result(result)

    def test_provider_schema_removes_provider_unsafe_metadata(self):
        schema = provider_schema(load_result_schema(Path.cwd()))

        self.assertNotIn("$schema", schema)
        self.assertNotIn("$id", schema)
        self.assertNotIn("title", schema)
        self.assertEqual(schema["additionalProperties"], False)
        question_schema = schema["properties"]["clarification"]["properties"]["question"]
        self.assertIn("anyOf", question_schema)
        self.assertNotIsInstance(question_schema.get("type"), list)


if __name__ == "__main__":
    unittest.main()
