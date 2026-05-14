import json
import os
import unittest
from pathlib import Path

from promptgate.config import load_config
from promptgate.llm import FakeProvider, OpenAIResponsesProvider, PromptGateRequest
from promptgate.prompts import build_promptgate_request
from promptgate.registry import load_registry
from promptgate.result import load_result_schema


class PromptGateLLMTest(unittest.TestCase):
    def test_fake_provider_returns_queued_json(self):
        provider = FakeProvider(['{"ok": true}'])
        request = PromptGateRequest(
            system_prompt="system",
            user_prompt="user",
            response_schema={"type": "object"},
            raw_prompt="raw",
        )

        self.assertEqual(provider.complete_json(request), '{"ok": true}')

    def test_fake_provider_raises_when_queue_is_empty(self):
        provider = FakeProvider([])
        request = PromptGateRequest(
            system_prompt="system",
            user_prompt="user",
            response_schema={"type": "object"},
            raw_prompt="raw",
        )

        with self.assertRaisesRegex(RuntimeError, "no fake provider responses"):
            provider.complete_json(request)

    def test_prompt_builder_includes_closed_world_registry(self):
        config = load_config(Path.cwd())
        registry = load_registry(config.registry_path)
        schema = load_result_schema(Path.cwd())

        request = build_promptgate_request(
            raw_prompt="$example-low-risk-skill 정리해줘",
            config=config,
            registry=registry,
            schema=schema,
        )

        self.assertIn("Return JSON only", request.system_prompt)
        self.assertIn("example-low-risk-skill", request.user_prompt)
        self.assertIn("closed-world", request.user_prompt)
        self.assertEqual(request.raw_prompt, "$example-low-risk-skill 정리해줘")

    def test_openai_provider_requires_api_key(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                OpenAIResponsesProvider.from_env()
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
