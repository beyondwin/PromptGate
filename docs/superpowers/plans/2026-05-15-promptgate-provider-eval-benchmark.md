# PromptGate Provider Eval Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in provider benchmark that runs PromptGate eval fixtures against the real runtime and reports field-level quality results.

**Architecture:** Keep the existing deterministic `python3 -m promptgate eval` path unchanged. Add `promptgate.eval_scoring` for field-level expected/result comparison and `promptgate.provider_eval` for case loading, provider execution, filtering, cost confirmation, text summary, and JSON report assembly. Wire `promptgate.cli` so `eval --provider` explicitly enters the provider benchmark path while tests use `FakeProvider` and never call the network.

**Tech Stack:** Python standard library `unittest`, dataclasses, argparse, pathlib, json, PyYAML-backed existing fixture validation, existing `PromptGateProvider` and `FakeProvider`, existing `python3 -m unittest` runner.

---

## Source Specification

- `docs/superpowers/specs/2026-05-15-promptgate-provider-eval-benchmark-design.md`

## File Structure

- Create: `promptgate/eval_scoring.py`
  - Owns pure field-level comparison between a runtime `PromptGateResult` dict and fixture `expected` dict.
  - Exposes `FieldFailure`, `CaseScore`, and `score_expected(result, expected)`.
- Create: `promptgate/provider_eval.py`
  - Owns fixture case loading, case id filtering, limit handling, case-local registry construction, provider runtime execution, report assembly, text formatting, JSON serialization, and provider cost confirmation helpers.
- Create: `tests/test_promptgate_eval_scoring.py`
  - Unit tests for exact, contains, negative contains, nested mappings, and partial expected scoring.
- Create: `tests/test_promptgate_provider_eval.py`
  - Unit tests for fake-provider benchmark execution, mismatch reporting, provider error continuation, case filters, report JSON shape, and case-local registry behavior.
- Modify: `promptgate/cli.py`
  - Parse `eval` as a subcommand-like path with provider benchmark flags.
  - Keep existing prompt CLI behavior unchanged.
- Modify: `tests/test_promptgate_cli.py`
  - Add CLI tests for deterministic eval preservation, provider path invocation, missing credentials, report writing, and non-TTY confirmation behavior.

No runtime judgment module changes are planned. Do not change `promptgate/guards.py`, `promptgate/runtime.py`, or provider prompt policy unless a test in this plan proves the provider benchmark cannot call existing runtime APIs.

## Task 1: Add Field-Level Eval Scorer

**Files:**
- Create: `tests/test_promptgate_eval_scoring.py`
- Create: `promptgate/eval_scoring.py`

- [ ] **Step 1: Write failing scorer tests**

Create `tests/test_promptgate_eval_scoring.py`:

```python
import unittest

from promptgate.eval_scoring import score_expected


RESULT = {
    "original_prompt": "원본",
    "refined_prompt": "한국어로 짧게 표로 정리해줘.",
    "intent": {
        "goal": "주문 처리 작업이 밀리지 않게 한다.",
        "domain": "engineering",
        "task_type": "plan",
        "confidence": 0.8,
    },
    "context": {
        "background": [],
        "constraints": [],
        "exclusions": ["code"],
        "output_preferences": ["Korean", "concise", "table"],
        "solution_candidates": ["큐"],
        "assumptions": [],
    },
    "clarification": {
        "needed": True,
        "question": "어떤 자료를 정리할까요?",
        "reason": "자료가 빠져 있습니다.",
    },
    "skill_handoff": {
        "mode": "auto",
        "explicit_skill_mention": None,
        "target_skill": None,
        "target_source": "none",
        "confidence": 0,
        "status": "no_match",
        "reason": None,
    },
    "safety": {
        "risk_level": "low",
        "requires_confirmation": False,
        "reason": None,
    },
}


class EvalScoringTest(unittest.TestCase):
    def test_scores_exact_and_contains_fields(self):
        score = score_expected(
            RESULT,
            {
                "status": "no_match",
                "target_source": "none",
                "target_skill": None,
                "requires_confirmation": False,
                "clarification_needed": True,
                "question_count": 1,
                "refined_prompt_includes": ["한국어", "표"],
                "goal_includes": ["주문 처리", "밀리지 않게"],
                "solution_candidates": ["큐"],
                "output_preferences": ["Korean", "concise"],
                "question_includes": ["어떤 자료"],
            },
        )

        self.assertTrue(score.passed)
        self.assertEqual(score.passed_fields, score.total_fields)
        self.assertEqual(score.failures, [])

    def test_records_field_failures(self):
        score = score_expected(
            RESULT,
            {
                "status": "auto_handoff",
                "target_skill": "example-low-risk-skill",
                "refined_prompt_includes": ["영어"],
            },
        )

        self.assertFalse(score.passed)
        self.assertEqual(
            [(failure.field, failure.expected, failure.actual) for failure in score.failures],
            [
                ("status", "auto_handoff", "no_match"),
                ("target_skill", "example-low-risk-skill", None),
                ("refined_prompt_includes", "영어", "한국어로 짧게 표로 정리해줘."),
            ],
        )

    def test_negative_contains_fields_fail_when_forbidden_text_appears(self):
        result = dict(RESULT)
        result["refined_prompt"] = "큐 is required for this design."

        score = score_expected(result, {"should_not_assume": ["queue is required", "큐 is required"]})

        self.assertFalse(score.passed)
        self.assertEqual(score.failures[0].field, "should_not_assume")
        self.assertEqual(score.failures[0].expected, "not containing 큐 is required")

    def test_partial_expected_only_scores_present_fields(self):
        score = score_expected(RESULT, {"clarification_needed": True})

        self.assertTrue(score.passed)
        self.assertEqual(score.total_fields, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the scorer tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_scoring
```

Expected result:

```text
ModuleNotFoundError: No module named 'promptgate.eval_scoring'
```

- [ ] **Step 3: Implement the scorer**

Create `promptgate/eval_scoring.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldFailure:
    field: str
    expected: Any
    actual: Any
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


@dataclass(frozen=True)
class CaseScore:
    total_fields: int
    passed_fields: int
    failures: list[FieldFailure]

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def field_score(self) -> float:
        if self.total_fields == 0:
            return 1.0
        return self.passed_fields / self.total_fields

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_fields": self.total_fields,
            "passed_fields": self.passed_fields,
            "field_score": self.field_score,
            "failures": [failure.as_dict() for failure in self.failures],
        }


EXACT_FIELD_PATHS = {
    "status": ("skill_handoff", "status"),
    "target_source": ("skill_handoff", "target_source"),
    "target_skill": ("skill_handoff", "target_skill"),
    "requires_confirmation": ("safety", "requires_confirmation"),
    "clarification_needed": ("clarification", "needed"),
}


CONTAINS_FIELD_PATHS = {
    "refined_prompt_includes": ("refined_prompt",),
    "goal_includes": ("intent", "goal"),
    "solution_candidates": ("context", "solution_candidates"),
    "output_preferences": ("context", "output_preferences"),
    "question_includes": ("clarification", "question"),
}


NEGATIVE_CONTAINS_FIELDS = {"should_not_assume", "exclusions"}


def score_expected(result: dict[str, Any], expected: dict[str, Any]) -> CaseScore:
    failures: list[FieldFailure] = []
    total = 0
    passed = 0

    for field, path in EXACT_FIELD_PATHS.items():
        if field not in expected:
            continue
        total += 1
        actual = _get_path(result, path)
        if actual == expected[field]:
            passed += 1
        else:
            failures.append(_failure(field, expected[field], actual))

    if "question_count" in expected:
        total += 1
        actual = _question_count(result)
        if actual == expected["question_count"]:
            passed += 1
        else:
            failures.append(_failure("question_count", expected["question_count"], actual))

    for field, path in CONTAINS_FIELD_PATHS.items():
        if field not in expected:
            continue
        for needle in expected[field]:
            total += 1
            actual = _get_path(result, path)
            haystack = _text_for_contains(actual)
            if _contains(haystack, needle):
                passed += 1
            else:
                failures.append(_failure(field, needle, actual))

    searchable_text = _searchable_text(result)
    for field in NEGATIVE_CONTAINS_FIELDS:
        if field not in expected:
            continue
        for forbidden in expected[field]:
            total += 1
            if _contains(searchable_text, forbidden):
                failures.append(
                    FieldFailure(
                        field=field,
                        expected=f"not containing {forbidden}",
                        actual=searchable_text,
                        message=f"{field} contained forbidden text {forbidden!r}",
                    )
                )
            else:
                passed += 1

    return CaseScore(total_fields=total, passed_fields=passed, failures=failures)


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _question_count(result: dict[str, Any]) -> int:
    question = str(_get_path(result, ("clarification", "question")) or "").strip()
    return 1 if question else 0


def _text_for_contains(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _searchable_text(result: dict[str, Any]) -> str:
    chunks = [
        result.get("refined_prompt"),
        _get_path(result, ("intent", "goal")),
        _get_path(result, ("clarification", "question")),
        _get_path(result, ("clarification", "reason")),
        _get_path(result, ("skill_handoff", "reason")),
        _get_path(result, ("safety", "reason")),
        _get_path(result, ("context", "constraints")),
        _get_path(result, ("context", "exclusions")),
        _get_path(result, ("context", "output_preferences")),
        _get_path(result, ("context", "solution_candidates")),
        _get_path(result, ("context", "assumptions")),
    ]
    return "\n".join(_text_for_contains(chunk) for chunk in chunks)


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _failure(field: str, expected: Any, actual: Any) -> FieldFailure:
    return FieldFailure(
        field=field,
        expected=expected,
        actual=actual,
        message=f"expected {field}={expected!r}, got {actual!r}",
    )
```

- [ ] **Step 4: Run the scorer tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_scoring
```

Expected result:

```text
Ran 4 tests
OK
```

- [ ] **Step 5: Commit scorer**

Run:

```bash
git add promptgate/eval_scoring.py tests/test_promptgate_eval_scoring.py
git commit -m "feat: add PromptGate eval scoring"
```

## Task 2: Add Provider Benchmark Runner

**Files:**
- Create: `tests/test_promptgate_provider_eval.py`
- Create: `promptgate/provider_eval.py`

- [ ] **Step 1: Write failing provider benchmark tests**

Create `tests/test_promptgate_provider_eval.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from promptgate.llm import FakeProvider, PromptGateRequest
from promptgate.provider_eval import (
    ProviderEvalOptions,
    build_case_registry,
    format_provider_eval_report,
    run_provider_eval,
    write_provider_eval_report,
)
from tests.test_promptgate_result import VALID_RESULT


class RaisingProvider:
    def complete_json(self, request: PromptGateRequest) -> str:
        raise RuntimeError("provider exploded")

    def repair_json(self, request: PromptGateRequest, invalid_output: str, error: str) -> str:
        raise RuntimeError("repair unavailable")


def write_fixture(tempdir: str, body: str) -> Path:
    path = Path(tempdir) / "cases.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class PromptGateProviderEvalTest(unittest.TestCase):
    def test_runs_cases_with_fake_provider_and_scores_passes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: simple_pass
    input: "정리좀"
    expected:
      status: no_match
      refined_prompt_includes:
        - "문장을"
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["passed"], 1)
        self.assertEqual(report.totals["failed"], 0)
        self.assertEqual(report.totals["error"], 0)
        self.assertEqual(report.cases[0].status, "passed")

    def test_records_field_mismatch_without_stopping(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: mismatch
    input: "정리좀"
    expected:
      status: auto_handoff
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["failed"], 1)
        self.assertEqual(report.cases[0].failures[0]["field"], "status")

    def test_provider_error_is_recorded_and_execution_continues(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: first_error
    input: "정리좀"
    expected:
      status: no_match
""",
            )

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=RaisingProvider(),
                project_root=Path.cwd(),
            )

        self.assertEqual(report.totals["error"], 1)
        self.assertEqual(report.cases[0].status, "error")
        self.assertIn("provider exploded", report.cases[0].error)

    def test_case_id_and_limit_filters_cases(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: keep
    input: "정리좀"
    expected:
      status: no_match
  - id: skip
    input: "다른 것"
    expected:
      status: no_match
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), case_ids=["keep"], limit=1, yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )

        self.assertEqual([case.case_id for case in report.cases], ["keep"])

    def test_case_local_registry_can_drive_explicit_skill_guard(self):
        registry = build_case_registry(
            [
                {
                    "id": "case-skill",
                    "risk_level": "low",
                    "auto_invocable": True,
                }
            ]
        )

        self.assertTrue(registry.has("case-skill"))
        self.assertEqual(registry.get("case-skill").description, "Eval fixture skill case-skill.")

    def test_formats_and_writes_report_json(self):
        with tempfile.TemporaryDirectory() as tempdir:
            write_fixture(
                tempdir,
                """
cases:
  - id: simple_pass
    input: "정리좀"
    expected:
      status: no_match
""",
            )
            provider = FakeProvider([json.dumps(VALID_RESULT, ensure_ascii=False)])
            report_path = Path(tempdir) / "report.json"

            report = run_provider_eval(
                ProviderEvalOptions(evals_dir=Path(tempdir), yes=True),
                provider=provider,
                project_root=Path.cwd(),
            )
            write_provider_eval_report(report, report_path)
            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertIn("Provider eval: 1 cases, 1 passed, 0 failed, 0 error", format_provider_eval_report(report))
        self.assertEqual(payload["totals"]["passed"], 1)
        self.assertEqual(payload["cases"][0]["case_id"], "simple_pass")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run provider benchmark tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_provider_eval
```

Expected result:

```text
ModuleNotFoundError: No module named 'promptgate.provider_eval'
```

- [ ] **Step 3: Implement provider benchmark runner**

Create `promptgate/provider_eval.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import load_config
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "totals": self.totals,
            "cases": [case.as_dict() for case in self.cases],
        }

    @property
    def ok(self) -> bool:
        return self.totals["failed"] == 0 and self.totals["error"] == 0


def load_provider_eval_cases(evals_dir: Path) -> list[ProviderEvalCase]:
    validate_all(evals_dir)
    cases: list[ProviderEvalCase] = []
    for path in sorted(evals_dir.glob("*.yaml")):
        payload = load_yaml(path)
        for case in payload["cases"]:
            cases.append(
                ProviderEvalCase(
                    file=str(path),
                    case_id=case["id"],
                    input=case["input"],
                    expected=case["expected"],
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


def _run_case(case: ProviderEvalCase, provider: PromptGateProvider, project_root: Path, config: Any) -> ProviderEvalCaseResult:
    try:
        registry = build_case_registry(case.registered_skills) if case.registered_skills else None
        result = run_promptgate(
            case.input,
            provider=provider,
            project_root=project_root,
            config=config,
            registry=registry,
        )
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
    except Exception as exc:
        return ProviderEvalCaseResult(
            file=case.file,
            case_id=case.case_id,
            input=case.input,
            status="error",
            field_score=0,
            failures=[],
            runtime_result=None,
            error=str(exc),
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
    field_score = sum(result.field_score for result in results) / len(results) if results else 1.0
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
```

- [ ] **Step 4: Run provider benchmark tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_provider_eval
```

Expected result:

```text
Ran 6 tests
OK
```

- [ ] **Step 5: Run scorer tests with provider tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_scoring tests.test_promptgate_provider_eval
```

Expected result:

```text
OK
```

- [ ] **Step 6: Commit provider benchmark runner**

Run:

```bash
git add promptgate/provider_eval.py tests/test_promptgate_provider_eval.py
git commit -m "feat: add PromptGate provider eval runner"
```

## Task 3: Wire Provider Benchmark CLI

**Files:**
- Modify: `promptgate/cli.py`
- Modify: `tests/test_promptgate_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append these tests to `PromptGateCLITest` in `tests/test_promptgate_cli.py`:

```python
    def test_eval_cli_remains_deterministic(self):
        from promptgate.cli import main

        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(["eval"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Deterministic runtime guard checks passed.", stdout.getvalue())

    def test_provider_eval_missing_key_returns_usage_error(self):
        from promptgate.cli import main

        previous = os.environ.pop("OPENAI_API_KEY", None)
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["eval", "--provider", "--yes", "--limit", "1"])
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertEqual(exit_code, 2)
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())

    def test_provider_eval_non_tty_without_yes_returns_usage_error(self):
        from promptgate.cli import main

        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "fake-key"
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["eval", "--provider", "--limit", "1"])
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertEqual(exit_code, 2)
        self.assertIn("--yes", stderr.getvalue())
```

Append this test class to `tests/test_promptgate_cli.py`:

```python
class PromptGateCLIProviderEvalTest(unittest.TestCase):
    def test_provider_eval_cli_can_use_injected_provider_for_tests(self):
        from promptgate.cli import main
        from promptgate.llm import FakeProvider

        provider_result = dict(VALID_RESULT)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                ["eval", "--provider", "--yes", "--case-id", "no_question_when_direction_clear"],
                provider_factory=lambda: FakeProvider([json.dumps(provider_result, ensure_ascii=False)]),
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Provider eval: 1 cases", stdout.getvalue())
        self.assertIn("Failures:", stdout.getvalue())

    def test_provider_eval_cli_writes_report_json(self):
        from promptgate.cli import main
        from promptgate.llm import FakeProvider

        provider_result = dict(VALID_RESULT)
        with tempfile.TemporaryDirectory() as tempdir:
            report_path = Path(tempdir) / "report.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "eval",
                        "--provider",
                        "--yes",
                        "--case-id",
                        "natural_rewrite",
                        "--report-json",
                        str(report_path),
                    ],
                    provider_factory=lambda: FakeProvider([json.dumps(provider_result, ensure_ascii=False)]),
                )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["metadata"]["case_count"], 1)
        self.assertEqual(payload["cases"][0]["case_id"], "natural_rewrite")
```

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli
```

Expected result:

```text
TypeError: main() got an unexpected keyword argument 'provider_factory'
```

or:

```text
unrecognized arguments: --provider
```

- [ ] **Step 3: Update CLI signature and eval routing**

Modify the import section and `main()` signature in `promptgate/cli.py`:

```python
import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from .llm import PromptGateProvider
from .runtime import run_promptgate
```

Change `main()` to accept a test-only provider factory:

```python
def main(
    argv: list[str] | None = None,
    provider_factory: Callable[[], PromptGateProvider] | None = None,
) -> int:
```

Replace the current `if args.prompt == ["eval"]` block with a pre-parser eval route before the prompt parser:

```python
    if active_argv and active_argv[0] == "eval":
        return _eval_main(active_argv[1:], provider_factory=provider_factory)
```

Keep the existing `doctor` and `hooks` checks before `_eval_main`.

- [ ] **Step 4: Add `_eval_main()` and cost guard**

Add this function to `promptgate/cli.py`:

```python
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

    preview_cases = filter_provider_eval_cases(
        load_provider_eval_cases(args.evals_dir),
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
```

- [ ] **Step 5: Run CLI tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_promptgate_cli
```

Expected result:

```text
OK
```

- [ ] **Step 6: Run deterministic eval runner tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_runner
python3 -m promptgate eval
```

Expected result:

```text
OK
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
```

- [ ] **Step 7: Commit CLI wiring**

Run:

```bash
git add promptgate/cli.py tests/test_promptgate_cli.py
git commit -m "feat: add provider eval CLI"
```

## Task 4: Final Verification And Documentation Check

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run focused provider benchmark tests**

Run:

```bash
python3 -m unittest tests.test_promptgate_eval_scoring tests.test_promptgate_provider_eval tests.test_promptgate_cli tests.test_promptgate_eval_runner
```

Expected result:

```text
OK
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
python3 -m unittest
```

Expected result:

```text
OK
```

- [ ] **Step 3: Run eval and package verification**

Run:

```bash
python3 scripts/validate-evals.py
python3 -m promptgate eval
env -u OPENAI_API_KEY python3 -m promptgate eval --provider --yes --limit 1
python3 scripts/verify-wheel-install.py
git diff --check
git status --short --branch
```

Expected result:

```text
Validated 5 eval file(s).
Validated 5 eval file(s).
Deterministic runtime guard checks passed.
OPENAI_API_KEY is required for eval --provider
Installed wheel smoke passed.
```

The provider command should exit with code `2`; record it as expected verification for the missing-key guard. `git diff --check` should print no output. `git status` should show only expected branch/ahead information and no unintended unstaged changes.

- [ ] **Step 4: If credentials are available, run one real provider smoke**

Run only when `OPENAI_API_KEY` is set and the user has approved provider cost:

```bash
python3 -m promptgate eval --provider --yes --limit 1 --report-json .promptgate/provider-eval-smoke.json
```

Expected result:

```text
Provider eval: 1 cases, ...
Field score: ...
```

The command may exit `0` or `1` depending on provider quality against the selected fixture. Treat either as a valid smoke result when `.promptgate/provider-eval-smoke.json` is written and contains one case. Do not commit `.promptgate/provider-eval-smoke.json`.

- [ ] **Step 5: Commit final verification-only documentation updates if any**

If implementation revealed a necessary README or docs update, commit it:

```bash
git add README.md docs/quickstart.md
git commit -m "docs: document PromptGate provider eval benchmark"
```

Skip this commit when no docs update is needed.

- [ ] **Step 6: Final report**

Report:

- commits created
- files changed
- verification commands and outcomes
- whether a real provider smoke was run or skipped
- explicit note that default deterministic eval behavior remains unchanged
- explicit note that judgment logic was not changed
