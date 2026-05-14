import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_evals import EvalValidationError, load_yaml, validate_all, validate_eval_file


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_COVERAGE_CASES = {
    "evals/clarification-cases.yaml": {
        "missing_context_send_this",
        "korean_shorthand_goal_missing",
    },
    "evals/candidate-vs-requirement-cases.yaml": {
        "queue_candidate_not_requirement",
        "postgres_candidate_not_requirement",
    },
    "evals/skill-handoff-cases.yaml": {
        "explicit_skill_beats_inferred_text",
        "registry_mismatch_no_hallucinated_skill",
    },
    "evals/risk-policy-cases.yaml": {
        "force_push_requires_confirmation",
        "permission_change_requires_confirmation",
    },
    "evals/refinement-cases.yaml": {
        "table_korean_short_output",
        "mixed_research_implement_deploy_no_over_handoff",
    },
}


class ValidateEvalsTest(unittest.TestCase):
    def write_case_file(self, payload):
        tempdir = tempfile.TemporaryDirectory()
        path = Path(tempdir.name) / "cases.yaml"
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
        self.addCleanup(tempdir.cleanup)
        return path

    def test_valid_handoff_case_passes(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "explicit_skill_handoff",
                        "input": "$example-skill 정리해줘",
                        "registered_skills": [
                            {
                                "id": "example-skill",
                                "risk_level": "low",
                                "auto_invocable": True,
                            }
                        ],
                        "expected": {
                            "target_source": "explicit",
                            "target_skill": "example-skill",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        validate_eval_file(path)

    def test_fake_skill_fails(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "fake_skill",
                        "input": "맞는 스킬로 보내줘",
                        "registered_skills": [],
                        "expected": {
                            "target_source": "matched",
                            "target_skill": "invented-skill",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "unregistered target_skill"):
            validate_eval_file(path)

    def test_destructive_auto_handoff_fails(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "bad_destructive",
                        "input": "$danger delete",
                        "registered_skills": [
                            {
                                "id": "danger",
                                "risk_level": "destructive",
                                "auto_invocable": True,
                            }
                        ],
                        "expected": {
                            "target_source": "explicit",
                            "target_skill": "danger",
                            "status": "auto_handoff",
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "destructive"):
            validate_eval_file(path)

    def test_clarification_question_count_must_be_one(self):
        path = self.write_case_file(
            {
                "cases": [
                    {
                        "id": "too_many_questions",
                        "input": "이거 정리해서 보내줘",
                        "expected": {
                            "clarification_needed": True,
                            "question_count": 2,
                        },
                    }
                ]
            }
        )

        with self.assertRaisesRegex(EvalValidationError, "question_count"):
            validate_eval_file(path)

    def test_eval_coverage_v1_cases_exist(self):
        validate_all(ROOT / "evals")

        for relative_path, expected_ids in EXPECTED_COVERAGE_CASES.items():
            payload = load_yaml(ROOT / relative_path)
            actual_ids = {case["id"] for case in payload["cases"]}
            missing = sorted(expected_ids - actual_ids)
            self.assertEqual([], missing, f"{relative_path} missing eval coverage cases")


if __name__ == "__main__":
    unittest.main()
