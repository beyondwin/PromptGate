from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .runtime import run_promptgate


def format_result(result: dict[str, Any], as_json: bool, debug: bool) -> str:
    if as_json or debug:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return result["refined_prompt"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PromptGate over a raw prompt.")
    parser.add_argument("prompt", nargs="*", help="Raw prompt to refine, or 'eval' to run evals.")
    parser.add_argument("--json", action="store_true", help="Print full PromptGateResult JSON.")
    parser.add_argument("--debug", action="store_true", help="Print full PromptGateResult JSON.")
    args = parser.parse_args(argv)

    if args.prompt == ["eval"]:
        from .eval_runner import run_eval_suite

        report = run_eval_suite()
        print(report)
        return 0

    raw_prompt = " ".join(args.prompt).strip()
    if not raw_prompt:
        parser.error("prompt is required")

    result = run_promptgate(raw_prompt)
    print(format_result(result, as_json=args.json, debug=args.debug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
