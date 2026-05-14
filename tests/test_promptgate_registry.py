import tempfile
import unittest
from pathlib import Path

import yaml

from promptgate.registry import RegistryError, SkillRegistry, load_registry


class PromptGateRegistryTest(unittest.TestCase):
    def test_loads_example_registry(self):
        registry = load_registry(Path("core/skill-registry/examples.yaml"))

        self.assertTrue(registry.has("example-low-risk-skill"))
        self.assertEqual(registry.get("example-destructive-skill").risk_level, "destructive")

    def test_prompt_payload_contains_closed_world_skill_data(self):
        registry = load_registry(Path("core/skill-registry/examples.yaml"))
        payload = registry.as_prompt_payload()

        self.assertEqual(payload[0]["id"], "example-low-risk-skill")
        self.assertIn("risk_level", payload[0])
        self.assertIn("auto_invocable", payload[0])

    def test_rejects_invalid_skill_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "registry.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "skills": [
                            {
                                "id": "-bad",
                                "description": "bad id",
                                "aliases": [],
                                "domains": [],
                                "task_types": [],
                                "trigger_phrases": [],
                                "risk_level": "low",
                                "auto_invocable": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RegistryError, "invalid skill id"):
                load_registry(path)

    def test_registry_can_be_built_from_inline_records(self):
        registry = SkillRegistry.from_records(
            [
                {
                    "id": "writer",
                    "description": "Rewrite text.",
                    "aliases": ["rewrite"],
                    "domains": ["writing"],
                    "task_types": ["rewrite"],
                    "trigger_phrases": ["정리해줘"],
                    "risk_level": "low",
                    "auto_invocable": True,
                }
            ]
        )

        self.assertTrue(registry.has("writer"))
        self.assertEqual(registry.get("writer").aliases, ["rewrite"])


if __name__ == "__main__":
    unittest.main()
