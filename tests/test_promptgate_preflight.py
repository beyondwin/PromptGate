import unittest

from promptgate.preflight import analyze_preflight


class PromptGatePreflightTest(unittest.TestCase):
    def test_bypass_prefix_uses_raw_pass_through(self):
        decision = analyze_preflight("#raw 코드말고 방향만")

        self.assertTrue(decision.bypass)
        self.assertEqual(decision.recommended_next, "raw-pass-through")
        self.assertIn("bypass_prefix", decision.risk_flags)

    def test_messy_dev_prompt_detects_candidate_and_exclusion(self):
        decision = analyze_preflight("코드말고 Redis 쓰면 되나 세션이랑 캐시 같이 쓰고 싶은데")

        self.assertFalse(decision.bypass)
        self.assertTrue(decision.is_vague)
        self.assertEqual(decision.domain_guess, "dev")
        self.assertEqual(decision.task_type_guess, "decide")
        self.assertEqual(decision.recommended_next, "prompt-normalizer")
        self.assertEqual(decision.recommended_skill_hint, "dev-task")
        self.assertIn("exclude_code", decision.risk_flags)
        self.assertIn("solution_candidate", decision.risk_flags)

    def test_clear_prompt_goes_direct(self):
        decision = analyze_preflight("README의 Quickstart 섹션을 5문장으로 요약해줘")

        self.assertFalse(decision.bypass)
        self.assertFalse(decision.is_vague)
        self.assertGreaterEqual(decision.clarity_score, 0.8)
        self.assertEqual(decision.recommended_next, "direct")

    def test_design_direction_prompt_routes_to_design_hint(self):
        decision = analyze_preflight("이 디자인 별론데 코드말고 방향만 잡아줘")

        self.assertTrue(decision.is_vague)
        self.assertEqual(decision.domain_guess, "design")
        self.assertEqual(decision.recommended_skill_hint, "design-brief")
        self.assertIn("exclude_code", decision.risk_flags)


if __name__ == "__main__":
    unittest.main()
