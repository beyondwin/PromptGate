# PromptGate Provider Eval Benchmark 설계

## 목표

PromptGate의 deterministic eval fixture를 실제 provider runtime 결과와 비교해, judgment 품질을 측정할 수 있는 opt-in benchmark를 추가한다.

이번 고도화의 목적은 판단 로직을 바로 바꾸는 것이 아니라, 새 golden fixture가 실제 provider 결과와 얼마나 맞는지 필드 단위로 드러내는 품질 루프를 만드는 것이다. 이후 clarification, skill matching, risk blocking, over-handoff 개선은 이 benchmark 결과를 기준선으로 삼는다.

성공 기준은 다음과 같다.

- 실제 provider로 eval case를 실행할 수 있다.
- fixture `expected`와 runtime result를 필드별로 비교한다.
- 실패는 어떤 case의 어떤 필드가 왜 빗나갔는지 리포트한다.
- 기본 `python3 -m promptgate eval`은 기존처럼 deterministic하고 빠르게 유지한다.
- provider 비용이 실수로 발생하지 않도록 명시적 opt-in과 confirmation을 둔다.
- JSON report를 저장해 이후 품질 개선 작업에서 비교 자료로 사용할 수 있다.

## 범위

포함한다.

- `python3 -m promptgate eval --provider` 형태의 opt-in provider benchmark
- fixture case loading and filtering
- provider runtime execution
- expected-field scorer
- CLI text summary
- optional JSON report output
- provider key/cost/error handling
- fake provider 기반 unit and CLI tests

제외한다.

- judgment logic 개선
- provider 결과 baseline 자동 갱신
- 여러 모델 동시 비교
- dashboard UI
- private conversation log 수집
- 기본 deterministic eval 동작 변경

## 사용자 흐름

기본 deterministic eval은 그대로 유지한다.

```bash
python3 -m promptgate eval
```

실제 provider benchmark는 명시적으로 실행한다.

```bash
python3 -m promptgate eval --provider
python3 -m promptgate eval --provider --evals-dir evals
python3 -m promptgate eval --provider --case-id explicit_skill_beats_inferred_text
python3 -m promptgate eval --provider --limit 5
python3 -m promptgate eval --provider --report-json .promptgate/eval-report.json
python3 -m promptgate eval --provider --yes --report-json .promptgate/eval-report.json
```

TTY에서 `--yes` 없이 provider benchmark를 실행하면 몇 개 case가 provider call을 발생시키는지 보여주고 확인을 요구한다. non-TTY에서는 `--yes` 없이는 실패한다.

## 아키텍처

기존 `eval_runner.py`는 deterministic smoke의 entry point로 유지하고, provider benchmark는 작은 전용 모듈들로 분리한다.

```text
evals/*.yaml
  -> eval_validation.validate_all()
  -> provider_eval.load_cases()
  -> run_promptgate(case.input, real provider, case/project config and registry)
  -> eval_scoring.compare(result, case.expected)
  -> ProviderEvalReport
  -> CLI text summary and optional JSON file
```

제안 모듈은 다음과 같다.

```text
promptgate/
  eval_scoring.py
  provider_eval.py
```

역할은 다음처럼 나눈다.

- `eval_validation.py`: fixture 구조가 유효한지 검증한다.
- `eval_scoring.py`: runtime result가 fixture `expected`를 만족하는지 평가한다.
- `provider_eval.py`: provider 실행, case별 result 수집, filtering, error handling, report assembly를 담당한다.
- `cli.py`: `eval --provider` 옵션을 받고 provider benchmark를 호출한다.
- `eval_runner.py`: 기존 deterministic eval behavior를 유지한다.

## Case Config And Registry

각 eval case는 기존 fixture format을 그대로 사용한다.

`registered_skills`가 case에 있으면 그 case-local registry가 benchmark 조건이다. 없으면 프로젝트 기본 registry/config를 사용한다.

이 규칙은 fixture 의미와 맞다.

- skill handoff fixture는 case-local registry가 테스트 조건이다.
- refinement and clarification fixture는 특정 skill registry에 의존하지 않아야 한다.
- risk policy fixture는 case-local risk level and auto-invocable setting을 우선해야 한다.

case-local registry를 사용할 때는 임시 `SkillRegistry`를 구성해 `run_promptgate()`에 직접 전달한다. config는 기본 project config를 사용하되, 필요한 경우 fixture-driven registry만 override한다.

## Scoring Model

Scoring은 expected field를 기준으로 한다. fixture에 없는 field는 평가하지 않는다.

Exact match fields:

- `status`
- `target_source`
- `target_skill`
- `requires_confirmation`
- `clarification_needed`
- `question_count`

Contains match fields:

- `refined_prompt_includes`
- `goal_includes`
- `solution_candidates`
- `output_preferences`
- `question_includes`

Negative contains fields:

- `should_not_assume`
- `exclusions`

Field mapping은 runtime result schema에 맞춘다.

- `status`, `target_source`, `target_skill`는 `skill_handoff`에서 읽는다.
- `requires_confirmation`은 `safety`에서 읽는다.
- `clarification_needed`, `question_count`, `question_includes`는 `clarification`에서 읽는다.
- `goal_includes`는 `intent.goal`에서 읽는다.
- `solution_candidates`, `output_preferences`, `exclusions`는 `context`에서 읽는다.
- `refined_prompt_includes`는 `refined_prompt`에서 읽는다.
- `should_not_assume`은 runtime result 전체의 relevant text fields에 금지 문구가 나타나지 않는지 확인한다.

각 case는 evaluated field count와 passed field count를 가진다. 전체 score는 field-level pass rate와 case-level pass rate를 함께 보여준다. v1에서 가중치는 모두 동일하게 둔다.

## Report Shape

Provider benchmark는 text summary와 optional JSON report를 생성한다.

CLI summary 예시는 다음과 같다.

```text
Provider eval: 18 cases, 13 passed, 3 failed, 2 error
Field score: 72.2%

Failures:
- evals/skill-handoff-cases.yaml::explicit_skill_beats_inferred_text
  expected target_skill=example-low-risk-skill, got null
- evals/risk-policy-cases.yaml::force_push_requires_confirmation
  expected status=blocked_by_risk, got no_match
```

JSON report는 다음 정보를 담는다.

- benchmark metadata: timestamp, model, evals_dir, filters, case count
- totals: passed, failed, error, skipped, field score
- cases:
  - `file`
  - `case_id`
  - `input`
  - `status`
  - `field_score`
  - `failures`
  - `runtime_result`
  - `error`

JSON report는 사람이 읽기 쉬운 stable key order로 저장한다. 이후 dashboard나 baseline comparison은 이 report를 재사용할 수 있다.

## Error Handling

Provider benchmark는 명시적 실행이므로 `OPENAI_API_KEY`가 없으면 error로 종료한다. 기존 deterministic eval은 provider key를 요구하지 않는다.

개별 case provider call이 실패하면 전체 benchmark를 즉시 중단하지 않는다. 해당 case를 `error`로 기록하고 다음 case를 계속 실행한다.

Invalid JSON, schema repair fallback, guard fallback은 runtime result로 그대로 평가한다. fallback이 expected와 맞지 않으면 scorer failure로 드러나야 한다.

`--report-json`이 있으면 실패나 error가 있더라도 report를 먼저 저장한 뒤 non-zero exit code로 종료한다.

## Cost Controls

Provider benchmark는 비용 발생 가능성을 명확히 다룬다.

- `--limit N`: 앞에서 N개 case만 실행한다.
- `--case-id ID`: 특정 case만 실행한다. 여러 번 지정할 수 있게 확장 가능하게 설계한다.
- `--yes`: 비용 경고 confirmation을 건너뛴다.
- TTY에서 `--yes` 없이 실행하면 provider call 수를 보여주고 confirmation을 요구한다.
- non-TTY에서 `--yes` 없이는 실패한다.

`--limit`과 `--case-id`가 함께 있으면 case id filter를 먼저 적용하고 그 결과에 limit을 적용한다.

## CLI Contract

`python3 -m promptgate eval`은 기존 deterministic output을 유지한다.

`python3 -m promptgate eval --provider`는 다음 exit code policy를 따른다.

- `0`: 모든 evaluated cases pass
- `1`: one or more scored cases failed or errored
- `2`: invalid CLI usage, missing provider credentials, or cost confirmation missing

The provider benchmark command should not hide failures behind a successful exit.

## Testing

필수 테스트는 다음과 같다.

- scorer unit tests:
  - exact match pass/fail
  - contains match pass/fail
  - negative contains pass/fail
  - nested field mapping
  - partial expected fields
- provider eval tests with `FakeProvider`:
  - all cases pass
  - field mismatch recorded
  - provider error recorded and execution continues
  - case-local registry overrides project registry
- CLI tests:
  - `eval` remains deterministic
  - `eval --provider --yes --limit 1` uses provider path
  - missing `OPENAI_API_KEY` errors for real provider path
  - `--case-id` filters cases
  - `--report-json` writes report before non-zero failure
  - non-TTY without `--yes` fails before provider calls

Default test suite must not make real provider calls.

## Acceptance Criteria

- `python3 -m promptgate eval` keeps the existing deterministic behavior.
- `python3 -m promptgate eval --provider --yes --limit 1` can execute a provider benchmark path when credentials are configured.
- Fake-provider tests cover scoring and report behavior without network calls.
- Field-level mismatches are visible in CLI output and JSON report.
- Provider benchmark cannot accidentally run in CI without `--yes`.
- JSON report contains stable per-case evidence for later quality improvement work.

## Follow-Up Work

After this provider benchmark exists, the next work should use its report to improve actual PromptGate judgment behavior.

Likely follow-up areas:

- clarification quality for Korean missing-context prompts
- solution candidate separation
- explicit skill priority and registry mismatch behavior
- high/destructive risk blocking
- multi-intent no-over-handoff behavior
- optional provider/model comparison once one-provider benchmark is stable
