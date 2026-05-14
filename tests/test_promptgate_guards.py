import copy
import unittest
from pathlib import Path

from promptgate.config import PromptGateConfig, load_config
from promptgate.guards import apply_guards, extract_explicit_skill_mention
from promptgate.registry import SkillRegistry, load_registry
from tests.test_promptgate_result import VALID_RESULT


class PromptGateGuardsTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(Path.cwd())
        self.registry = load_registry(self.config.registry_path)

    def test_extract_explicit_skill_mention(self):
        self.assertEqual(extract_explicit_skill_mention("$example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertEqual(extract_explicit_skill_mention("@example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertEqual(extract_explicit_skill_mention("/example-low-risk-skill 정리해줘"), "example-low-risk-skill")
        self.assertIsNone(extract_explicit_skill_mention("정리해줘"))

    def test_original_prompt_is_authoritative(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["original_prompt"] = "changed"

        result = apply_guards(draft, raw_prompt="raw", config=self.config, registry=self.registry)

        self.assertEqual(result["original_prompt"], "raw")

    def test_missing_explicit_skill_becomes_skill_not_found(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "missing-skill"
        draft["skill_handoff"]["target_source"] = "explicit"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="$missing-skill 정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "skill_not_found")
        self.assertIsNone(result["skill_handoff"]["target_skill"])
        self.assertEqual(result["skill_handoff"]["target_source"], "none")

    def test_unregistered_inferred_skill_becomes_no_match(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "invented-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "no_match")
        self.assertIsNone(result["skill_handoff"]["target_skill"])

    def test_destructive_skill_blocks_auto_handoff(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-destructive-skill"
        draft["skill_handoff"]["target_source"] = "explicit"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 1

        result = apply_guards(
            draft,
            raw_prompt="$example-destructive-skill 전부 삭제해줘",
            config=self.config,
            registry=self.registry,
        )

        self.assertEqual(result["skill_handoff"]["status"], "blocked_by_risk")
        self.assertTrue(result["safety"]["requires_confirmation"])
        self.assertEqual(result["safety"]["risk_level"], "destructive")

    def test_suggest_mode_rewrites_auto_handoff(self):
        suggest_config = PromptGateConfig.from_mapping({"mode": "suggest"}, project_root=Path.cwd())
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-low-risk-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 0.95

        result = apply_guards(draft, raw_prompt="정리해줘", config=suggest_config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "suggested")

    def test_off_mode_disables_handoff(self):
        off_config = PromptGateConfig.from_mapping({"mode": "off"}, project_root=Path.cwd())
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "example-low-risk-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"

        result = apply_guards(draft, raw_prompt="정리해줘", config=off_config, registry=self.registry)

        self.assertEqual(result["skill_handoff"]["status"], "disabled")
        self.assertIsNone(result["skill_handoff"]["target_skill"])

    def test_empty_refined_prompt_falls_back_to_raw_prompt(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["refined_prompt"] = " "

        result = apply_guards(draft, raw_prompt="정리해줘", config=self.config, registry=self.registry)

        self.assertEqual(result["refined_prompt"], "정리해줘")

    def test_missing_clarification_question_gets_generic_question(self):
        draft = copy.deepcopy(VALID_RESULT)
        draft["clarification"]["needed"] = True
        draft["clarification"]["question"] = ""

        result = apply_guards(draft, raw_prompt="이거 정리해서 보내줘", config=self.config, registry=self.registry)

        self.assertEqual(result["clarification"]["question"], "어떤 결과물을 원하시는지 한 가지만 알려주세요.")

    def test_auto_invocable_false_prevents_auto_handoff(self):
        registry = SkillRegistry.from_records(
            [
                {
                    "id": "manual-skill",
                    "description": "Manual review skill.",
                    "aliases": [],
                    "domains": ["ops"],
                    "task_types": ["review"],
                    "trigger_phrases": [],
                    "risk_level": "low",
                    "auto_invocable": False,
                }
            ]
        )
        draft = copy.deepcopy(VALID_RESULT)
        draft["skill_handoff"]["target_skill"] = "manual-skill"
        draft["skill_handoff"]["target_source"] = "matched"
        draft["skill_handoff"]["status"] = "auto_handoff"
        draft["skill_handoff"]["confidence"] = 0.99

        result = apply_guards(draft, raw_prompt="검토해줘", config=self.config, registry=registry)

        self.assertEqual(result["skill_handoff"]["status"], "suggested")


if __name__ == "__main__":
    unittest.main()
