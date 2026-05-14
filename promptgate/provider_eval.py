from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import PromptGateConfig, load_config
from .eval_scoring import score_expected
from .eval_validation import load_yaml, validate_all
from .llm import OpenAIResponsesProvider, PromptGateProvider
from .registry import SkillRegistry
from .resources import runtime_root
from .runtime import run_promptgate


@dataclass(frozen=True)
class ProviderEvalOptions:
    evals_dir: Path
    case_ids: list[str] | None = None
    limit: int | None = None
    yes: bool = False
    report_json: Path | None = None


@dataclass(frozen=True)
class ProviderEvalCase:
    file: str
    case_id: str
    input: str
    expected: dict[str, Any]
    registered_skills: list[dict[str, Any]]


@dataclass(frozen=True)
class ProviderEvalCaseResult:
    file: str
    case_id: str
    input: str
    status: str
    field_score: float
    failures: list[dict[str, Any]]
    runtime_result: dict[str, Any] | None
    error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "case_id": self.case_id,
            "input": self.input,
            "status": self.status,
            "field_score": self.field_score,
            "failures": self.failures,
            "runtime_result": self.runtime_result,
            "error": self.error,
        }


@dataclass(frozen=True)
class ProviderEvalReport:
    metadata: dict[str, Any]
    totals: dict[str, Any]
    cases: list[ProviderEvalCaseResult]

    @property
    def ok(self) -> bool:
        return self.totals["failed"] == 0 and self.totals["error"] == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "totals": self.totals,
            "cases": [case.as_dict() for case in self.cases],
        }


def load_provider_eval_cases(evals_dir: Path) -> list[ProviderEvalCase]:
    paths = validate_all(evals_dir)
    cases: list[ProviderEvalCase] = []
    for path in paths:
        payload = load_yaml(path)
        for case in payload["cases"]:
            cases.append(
                ProviderEvalCase(
                    file=str(path),
                    case_id=case["id"],
                    input=case["input"],
                    expected=dict(case["expected"]),
                    registered_skills=list(case.get("registered_skills", [])),
                )
            )
    return cases


def filter_provider_eval_cases(
    cases: list[ProviderEvalCase],
    case_ids: list[str] | None,
    limit: int | None,
) -> list[ProviderEvalCase]:
    filtered = cases
    if case_ids:
        wanted = set(case_ids)
        filtered = [case for case in filtered if case.case_id in wanted]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def build_case_registry(records: list[dict[str, Any]]) -> SkillRegistry:
    expanded = []
    for record in records:
        skill_id = record["id"]
        expanded.append(
            {
                "id": skill_id,
                "description": record.get("description", f"Eval fixture skill {skill_id}."),
                "aliases": list(record.get("aliases", [])),
                "domains": list(record.get("domains", ["eval"])),
                "task_types": list(record.get("task_types", ["eval"])),
                "trigger_phrases": list(record.get("trigger_phrases", [])),
                "risk_level": record["risk_level"],
                "auto_invocable": record["auto_invocable"],
                "platform_names": dict(record.get("platform_names", {})),
            }
        )
    return SkillRegistry.from_records(expanded)


def run_provider_eval(
    options: ProviderEvalOptions,
    provider: PromptGateProvider | None = None,
    project_root: Path | None = None,
) -> ProviderEvalReport:
    root = runtime_root(project_root)
    evals_dir = options.evals_dir if options.evals_dir.is_absolute() else root / options.evals_dir
    all_cases = load_provider_eval_cases(evals_dir)
    cases = filter_provider_eval_cases(all_cases, options.case_ids, options.limit)
    active_provider = provider or OpenAIResponsesProvider.from_env()
    config = load_config(root)
    results = [
        _run_case(case, provider=active_provider, project_root=root, config=config)
        for case in cases
    ]
    return _build_report(options, evals_dir, all_cases, cases, results)


def format_provider_eval_report(report: ProviderEvalReport) -> str:
    case_count = len(report.cases)
    lines = [
        (
            f"Provider eval: {case_count} cases, {report.totals['passed']} passed, "
            f"{report.totals['failed']} failed, {report.totals['error']} error"
        ),
        f"Field score: {report.totals['field_score'] * 100:.1f}%",
    ]
    failing = [case for case in report.cases if case.status in {"failed", "error"}]
    if failing:
        lines.append("")
        lines.append("Failures:")
        for case in failing:
            lines.append(f"- {case.file}::{case.case_id}")
            if case.error:
                lines.append(f"  error: {case.error}")
            for failure in case.failures:
                lines.append(f"  {failure['message']}")
    return "\n".join(lines)


def write_provider_eval_report(report: ProviderEvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_case(
    case: ProviderEvalCase,
    provider: PromptGateProvider,
    project_root: Path,
    config: PromptGateConfig,
) -> ProviderEvalCaseResult:
    try:
        registry = build_case_registry(case.registered_skills) if case.registered_skills else None
        result = run_promptgate(
            case.input,
            provider=provider,
            project_root=project_root,
            config=config,
            registry=registry,
        )
    except Exception as exc:
        return _error_result(case, str(exc), runtime_result=None)

    provider_error = _provider_error(result)
    if provider_error:
        return _error_result(case, provider_error, runtime_result=result)

    score = score_expected(result, case.expected)
    return ProviderEvalCaseResult(
        file=case.file,
        case_id=case.case_id,
        input=case.input,
        status="passed" if score.passed else "failed",
        field_score=score.field_score,
        failures=[failure.as_dict() for failure in score.failures],
        runtime_result=result,
        error=None,
    )


def _build_report(
    options: ProviderEvalOptions,
    evals_dir: Path,
    all_cases: list[ProviderEvalCase],
    evaluated_cases: list[ProviderEvalCase],
    results: list[ProviderEvalCaseResult],
) -> ProviderEvalReport:
    passed = sum(1 for result in results if result.status == "passed")
    failed = sum(1 for result in results if result.status == "failed")
    errors = sum(1 for result in results if result.status == "error")
    field_score = _field_score(results)
    return ProviderEvalReport(
        metadata={
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "evals_dir": str(evals_dir),
            "filters": {
                "case_ids": options.case_ids or [],
                "limit": options.limit,
            },
            "case_count": len(evaluated_cases),
            "available_case_count": len(all_cases),
        },
        totals={
            "passed": passed,
            "failed": failed,
            "error": errors,
            "skipped": len(all_cases) - len(evaluated_cases),
            "field_score": field_score,
        },
        cases=results,
    )


def _field_score(results: list[ProviderEvalCaseResult]) -> float:
    if not results:
        return 1.0
    return sum(result.field_score for result in results) / len(results)


def _error_result(
    case: ProviderEvalCase,
    error: str,
    runtime_result: dict[str, Any] | None,
) -> ProviderEvalCaseResult:
    return ProviderEvalCaseResult(
        file=case.file,
        case_id=case.case_id,
        input=case.input,
        status="error",
        field_score=0,
        failures=[],
        runtime_result=runtime_result,
        error=error,
    )


def _provider_error(result: dict[str, Any]) -> str | None:
    reason = _get_path(result, ("skill_handoff", "reason"))
    if isinstance(reason, str) and reason.startswith("Provider error:"):
        return reason
    return None


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
