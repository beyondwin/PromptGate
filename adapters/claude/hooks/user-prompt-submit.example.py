#!/usr/bin/env python3
import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    prompt = payload.get("prompt", "")
    additional_context = (
        "PromptGate adapter active. Refine the submitted prompt before downstream work. "
        "If the prompt explicitly names a registered skill, hand off the refined prompt to that skill. "
        "Do not ask for handoff confirmation unless the matched skill is high-risk or destructive. "
        f"Original prompt: {prompt}"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": additional_context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
