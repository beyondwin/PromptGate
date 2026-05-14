from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from .llm import PromptGateProvider
from .runtime import run_promptgate


def format_result(result: dict[str, Any], as_json: bool, debug: bool) -> str:
    if as_json or debug:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return result["refined_prompt"]


def main(
    argv: list[str] | None = None,
    provider_factory: Callable[[], PromptGateProvider] | None = None,
) -> int:
    active_argv = list(sys.argv[1:] if argv is None else argv)
    if active_argv and active_argv[0] == "doctor":
        return _doctor_main(active_argv[1:])
    if active_argv and active_argv[0] == "hooks":
        return _hooks_main(active_argv[1:])
    if active_argv and active_argv[0] == "eval":
        return _eval_main(active_argv[1:], provider_factory=provider_factory)

    parser = argparse.ArgumentParser(description="Run PromptGate over a raw prompt.")
    parser.add_argument("prompt", nargs="*", help="Raw prompt to refine, or 'eval' to run evals.")
    parser.add_argument("--json", action="store_true", help="Print full PromptGateResult JSON.")
    parser.add_argument("--debug", action="store_true", help="Print full PromptGateResult JSON.")
    args = parser.parse_args(active_argv)

    raw_prompt = " ".join(args.prompt).strip()
    if not raw_prompt:
        parser.error("prompt is required")

    result = run_promptgate(raw_prompt)
    print(format_result(result, as_json=args.json, debug=args.debug))
    return 0


def _eval_main(
    argv: list[str],
    provider_factory: Callable[[], PromptGateProvider] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Run PromptGate evals.")
    parser.add_argument("--provider", action="store_true", help="Run eval fixtures against the real provider.")
    parser.add_argument("--evals-dir", type=Path, default=Path("evals"))
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--yes", action="store_true", help="Confirm provider cost for non-interactive runs.")
    args = parser.parse_args(argv)

    if not args.provider:
        from .eval_runner import run_eval_suite

        report = run_eval_suite()
        print(report)
        return 0

    if args.limit is not None and args.limit < 1:
        print("--limit must be at least 1", file=sys.stderr)
        return 2

    if provider_factory is None and not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for eval --provider", file=sys.stderr)
        return 2

    from .provider_eval import (
        ProviderEvalOptions,
        filter_provider_eval_cases,
        format_provider_eval_report,
        load_provider_eval_cases,
        run_provider_eval,
        write_provider_eval_report,
    )
    from .resources import runtime_root

    root = runtime_root(Path.cwd())
    evals_dir = args.evals_dir if args.evals_dir.is_absolute() else root / args.evals_dir
    preview_cases = filter_provider_eval_cases(
        load_provider_eval_cases(evals_dir),
        args.case_ids,
        args.limit,
    )
    if not args.yes:
        if not sys.stdin.isatty():
            print("eval --provider requires --yes in non-interactive mode", file=sys.stderr)
            return 2
        answer = input(f"{len(preview_cases)} cases will call the provider. Continue? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Provider eval cancelled.", file=sys.stderr)
            return 2

    report = run_provider_eval(
        ProviderEvalOptions(
            evals_dir=args.evals_dir,
            case_ids=args.case_ids,
            limit=args.limit,
            yes=args.yes,
            report_json=args.report_json,
        ),
        provider=provider_factory() if provider_factory else None,
        project_root=Path.cwd(),
    )
    if args.report_json:
        write_provider_eval_report(report, args.report_json)
    print(format_provider_eval_report(report))
    return 0 if report.ok else 1


def _doctor_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify PromptGate hook readiness.")
    parser.add_argument("--json", action="store_true", help="Print structured doctor report JSON.")
    parser.add_argument("--provider", action="store_true", help="Run an optional real provider smoke check.")
    args = parser.parse_args(argv)

    from .doctor import format_doctor_report, run_doctor

    report = run_doctor(provider=args.provider)
    print(format_doctor_report(report, as_json=args.json))
    return 0 if report.ok else 1


def _hooks_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Manage PromptGate hooks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser(
        "install",
        help="Install PromptGate hook configuration.",
    )
    install_parser.add_argument("--adapter", choices=("codex", "claude"), required=True)
    install_parser.add_argument("--target", type=Path)
    install_parser.add_argument("--apply", action="store_true")
    install_parser.add_argument("--json", action="store_true")
    install_parser.add_argument("--skip-doctor", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "install":
        from .hooks import format_hook_install_report, install_hook

        report = install_hook(
            args.adapter,
            target=args.target,
            apply=args.apply,
            skip_doctor=args.skip_doctor,
        )
        print(format_hook_install_report(report, as_json=args.json))
        return 0 if report.ok else 1

    parser.error(f"unsupported hooks command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
