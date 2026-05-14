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
    active_argv = list(sys.argv[1:] if argv is None else argv)
    if active_argv and active_argv[0] == "doctor":
        return _doctor_main(active_argv[1:])

    parser = argparse.ArgumentParser(description="Run PromptGate over a raw prompt.")
    parser.add_argument("prompt", nargs="*", help="Raw prompt to refine, or 'eval' to run evals.")
    parser.add_argument("--json", action="store_true", help="Print full PromptGateResult JSON.")
    parser.add_argument("--debug", action="store_true", help="Print full PromptGateResult JSON.")
    args = parser.parse_args(active_argv)

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


def _doctor_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify PromptGate hook readiness.")
    parser.add_argument("--json", action="store_true", help="Print structured doctor report JSON.")
    parser.add_argument("--provider", action="store_true", help="Run an optional real provider smoke check.")
    args = parser.parse_args(argv)

    from .doctor import format_doctor_report, run_doctor

    report = run_doctor(provider=args.provider)
    print(format_doctor_report(report, as_json=args.json))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
