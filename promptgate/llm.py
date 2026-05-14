from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol


@dataclass(frozen=True)
class PromptGateRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict
    raw_prompt: str


class PromptGateProvider(Protocol):
    def complete_json(self, request: PromptGateRequest) -> str:
        raise NotImplementedError

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        raise NotImplementedError


class FakeProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def complete_json(self, request: PromptGateRequest) -> str:
        if not self._responses:
            raise RuntimeError("no fake provider responses available")
        return self._responses.pop(0)

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        return self.complete_json(request)


class OpenAIResponsesProvider:
    def __init__(self, api_key: str, model: str = "gpt-5"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    @classmethod
    def from_env(cls) -> "OpenAIResponsesProvider":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required to use the OpenAI provider")
        model = os.environ.get("PROMPTGATE_OPENAI_MODEL", "gpt-5")
        return cls(api_key=api_key, model=model)

    def complete_json(self, request: PromptGateRequest) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "promptgate_result",
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
            store=False,
        )
        return response.output_text

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        repair_request = PromptGateRequest(
            system_prompt=request.system_prompt,
            user_prompt=(
                request.user_prompt
                + "\n\nThe previous JSON output was invalid.\n"
                + f"Validation error: {error}\n"
                + "Return a corrected PromptGateResult JSON object only.\n"
                + "Invalid output:\n"
                + invalid_output
            ),
            response_schema=request.response_schema,
            raw_prompt=request.raw_prompt,
        )
        return self.complete_json(repair_request)
