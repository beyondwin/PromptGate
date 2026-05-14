import tempfile
import unittest
from pathlib import Path

import yaml

from promptgate.config import ConfigError, PromptGateConfig, load_config


class PromptGateConfigTest(unittest.TestCase):
    def test_loads_example_config_from_project_root(self):
        config = load_config(Path.cwd())

        self.assertEqual(config.mode, "auto")
        self.assertEqual(config.auto_handoff_threshold, 0.78)
        self.assertEqual(config.registry_path, Path.cwd() / "core/skill-registry/examples.yaml")
        self.assertEqual(config.risk_policy["high"], "suggest")

    def test_rejects_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config_path = root / "promptgate.config.yaml"
            config_path.write_text(
                yaml.safe_dump({"promptgate": {"mode": "fast"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "invalid mode"):
                load_config(root)

    def test_defaults_missing_optional_sections(self):
        config = PromptGateConfig.from_mapping(
            {"mode": "suggest"},
            project_root=Path.cwd(),
        )

        self.assertEqual(config.mode, "suggest")
        self.assertEqual(config.auto_handoff_threshold, 0.78)
        self.assertEqual(config.max_recommendations, 3)
        self.assertEqual(config.risk_policy["destructive"], "require_confirmation")


if __name__ == "__main__":
    unittest.main()
