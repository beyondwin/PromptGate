import unittest

from promptgate.eval_scoring import score_expected


RESULT = {
    "original_prompt": "원본",
    "refined_prompt": "한국어로 짧게 표로 정리해줘.",
    "intent": {
        "goal": "주문 처리 작업이 밀리지 않게 한다.",
        "domain": "engineering",
        "task_type": "plan",
        "confidence": 0.8,
    },
    "context": {
        "background": [],
        "constraints": [],
        "exclusions": ["code"],
        "output_preferences": ["Korean", "concise", "table"],
        "solution_candidates": ["큐"],
        "assumptions": [],
    },
    "clarification": {
        "needed": True,
        "question": "어떤 자료를 정리할까요?",
        "reason": "자료가 빠져 있습니다.",
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


class EvalScoringTest(unittest.TestCase):
    def test_scores_exact_and_contains_fields(self):
        score = score_expected(
            RESULT,
            {
                "status": "no_match",
                "target_source": "none",
                "target_skill": None,
                "requires_confirmation": False,
                "clarification_needed": True,
                "question_count": 1,
                "refined_prompt_includes": ["한국어", "표"],
                "goal_includes": ["주문 처리", "밀리지 않게"],
                "solution_candidates": ["큐"],
                "output_preferences": ["Korean", "concise"],
                "question_includes": ["어떤 자료"],
            },
        )

        self.assertTrue(score.passed)
        self.assertEqual(score.passed_fields, score.total_fields)
        self.assertEqual(score.failures, [])

    def test_records_field_failures(self):
        score = score_expected(
            RESULT,
            {
                "status": "auto_handoff",
                "target_skill": "example-low-risk-skill",
                "refined_prompt_includes": ["영어"],
            },
        )

        self.assertFalse(score.passed)
        self.assertEqual(
            [(failure.field, failure.expected, failure.actual) for failure in score.failures],
            [
                ("status", "auto_handoff", "no_match"),
                ("target_skill", "example-low-risk-skill", None),
                ("refined_prompt_includes", "영어", "한국어로 짧게 표로 정리해줘."),
            ],
        )

    def test_negative_contains_fields_fail_when_forbidden_text_appears(self):
        result = dict(RESULT)
        result["refined_prompt"] = "큐 is required for this design."

        score = score_expected(result, {"should_not_assume": ["queue is required", "큐 is required"]})

        self.assertFalse(score.passed)
        self.assertEqual(score.failures[0].field, "should_not_assume")
        self.assertEqual(score.failures[0].expected, "not containing 큐 is required")

    def test_partial_expected_only_scores_present_fields(self):
        score = score_expected(RESULT, {"clarification_needed": True})

        self.assertTrue(score.passed)
        self.assertEqual(score.total_fields, 1)


if __name__ == "__main__":
    unittest.main()
