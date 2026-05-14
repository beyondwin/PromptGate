import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptGateAdapterHookTest(unittest.TestCase):
    def test_codex_hook_emits_valid_json_without_openai_key(self):
        output = self._run_hook("adapters/codex/hooks/user-prompt-submit.example.py")

        parsed = json.loads(output)
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("Original prompt", context)

    def test_claude_hook_emits_valid_json_without_openai_key(self):
        output = self._run_hook("adapters/claude/hooks/user-prompt-submit.example.py")

        parsed = json.loads(output)
        context = parsed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PromptGate runtime unavailable", context)
        self.assertIn("Original prompt", context)

    def test_codex_hook_bypass_path(self):
        output = self._run_hook(
            "adapters/codex/hooks/user-prompt-submit.example.py",
            prompt="#raw 그대로",
        )

        parsed = json.loads(output)
        self.assertIn(
            "PromptGate bypass active",
            parsed["hookSpecificOutput"]["additionalContext"],
        )

    def _run_hook(self, script_path, prompt="코드말고 방향만"):
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / script_path)],
            input=json.dumps({"prompt": prompt}, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=env,
            check=True,
        )
        self.assertEqual(completed.stderr, "")
        return completed.stdout


if __name__ == "__main__":
    unittest.main()
