# PromptGate Eval Coverage v1 설계

## 목표

PromptGate의 판단 품질을 개선하기 전에, 먼저 헷갈리기 쉬운 messy prompt 사례를 eval fixture로 고정한다. 이번 작업의 산출물은 더 넓은 golden fixture coverage이며, matching, risk, clarification, guard 로직 자체는 바꾸지 않는다.

성공 기준은 다음과 같다.

- 기존 fixture 형식으로 품질 기준선을 넓힌다.
- 한국어 구어체, 맥락 부족, solution-candidate 오해, 위험 작업, 명시적 skill 언급, 출력 제약, multi-intent, registry mismatch 유형을 포함한다.
- `python3 scripts/validate-evals.py`와 `python3 -m promptgate eval`이 계속 통과한다.
- 이후 판단 로직 개선 작업이 새 fixture를 회귀 기준으로 사용할 수 있다.

## 범위

이번 spec은 eval coverage 확장만 다룬다.

포함한다.

- 기존 `evals/*.yaml` 파일에 high-signal case 추가
- 이 spec 안에 eval coverage taxonomy 문서화
- fixture 검증기가 현재 표현하지 못하는 필드가 있을 때만 최소 확장
- 기존 deterministic eval runner 통과 확인

제외한다.

- runtime 판단 로직 변경
- provider 호출 기반 benchmark
- 실제 private conversation log 수집
- trace/report 기능
- public dashboard 또는 점수 시각화

## Coverage Taxonomy

새 eval case는 아래 8개 유형을 기준으로 설계한다. 각 유형은 최소 1개 이상 fixture에 반영하되, 기존 coverage와 중복되는 경우에는 더 구체적인 변형 케이스를 추가한다.

### 1. Clarification Required

사용자가 "이거", "저거", "정리해줘"처럼 필요한 대상이나 결과물을 빠뜨린 경우 clarification이 필요해야 한다.

예상 검증 포인트:

- `clarification_needed: true`
- `question_count: 1`
- 질문이 빠진 결과물, 대상, 입력 자료 중 하나를 묻는다.

### 2. Solution Candidate Separation

사용자가 "Redis 쓰면 되나", "큐 쓰면 될 것 같은데"처럼 해결책을 제안하지만 요구사항으로 확정하지 않은 경우, PromptGate는 이를 후보로 다뤄야 한다.

예상 검증 포인트:

- `solution_candidates`에 제안 기술이 들어간다.
- `goal_includes`는 사용자의 실제 목표를 반영한다.
- `should_not_assume` 또는 `exclusions`로 후보를 확정 요구사항처럼 취급하지 않는다.

### 3. Explicit Skill Priority

명시적으로 `$skill-name`이 언급된 경우, 약한 자연어 추론보다 explicit mention이 우선한다. 단, registry에 없는 skill은 자동 handoff하지 않는다.

예상 검증 포인트:

- 등록된 explicit skill은 `target_source: explicit`
- 없는 explicit skill은 `status: skill_not_found`
- 약한 inferred match가 explicit mention을 덮어쓰지 않는다.

### 4. Risk And Confirmation

삭제, 배포, 권한 변경, 강제 push 같은 위험하거나 되돌리기 어려운 작업은 자동 handoff를 막아야 한다.

예상 검증 포인트:

- high/destructive skill은 `auto_handoff`가 아니다.
- `requires_confirmation`이 꺼지지 않는다.
- 위험 작업의 이유가 expected 필드로 표현 가능해야 한다.

### 5. Output Constraint Preservation

"코드 말고 방향만", "짧게", "표로", "한국어로" 같은 출력 제약은 refined prompt에 보존되어야 한다.

예상 검증 포인트:

- `refined_prompt_includes`에 출력 제약이 포함된다.
- 출력 제약 때문에 불필요한 skill handoff가 발생하지 않는다.

### 6. Korean Messy Prompt

한국어 구어체, 생략, 혼합 의도, 짧은 단어 중심 prompt를 fixture에 추가한다. 목표는 한국어 입력의 실제 사용감을 반영하는 것이다.

예상 검증 포인트:

- `goal_includes`가 생략된 의도를 과도하게 확정하지 않는다.
- 입력만으로 목표나 결과물이 확정되지 않으면 clarification을 요구한다.
- 명확한 경우에는 불필요하게 질문하지 않는다.

### 7. Multi-Intent Without Over-Handoff

한 prompt 안에 조사, 구현, 배포, 문서화 같은 여러 의도가 섞여 있을 때, PromptGate는 가장 안전한 다음 행동을 정리하되 과도하게 특정 skill로 자동 handoff하지 않아야 한다.

예상 검증 포인트:

- `solution_candidates`나 `output_preferences`로 의도를 분리한다.
- ambiguous하거나 high-risk가 섞이면 자동 handoff하지 않는다.
- 질문이 필요한 경우 clarification으로 보낸다.

### 8. Registry Mismatch

사용자의 요청이 어떤 skill처럼 보이지만 registry에 해당 skill이 없거나, risk policy상 자동 실행이 부적절한 경우를 커버한다.

예상 검증 포인트:

- registry에 없는 skill은 `target_skill: null`
- `status`는 `no_match` 또는 `skill_not_found`
- hallucinated skill id가 결과에 남지 않는다.

## Fixture Placement

기존 eval 파일을 유지하고, 새 case는 의미상 가장 가까운 파일에 추가한다.

- `evals/clarification-cases.yaml`: clarification required, Korean missing-context prompt
- `evals/candidate-vs-requirement-cases.yaml`: solution candidate separation
- `evals/skill-handoff-cases.yaml`: explicit skill priority, registry mismatch
- `evals/risk-policy-cases.yaml`: high/destructive confirmation behavior
- `evals/refinement-cases.yaml`: output constraint preservation, messy Korean refinement

새 파일은 만들지 않는다. 기존 파일별 관심사가 이미 충분히 분리되어 있고, 새 파일을 추가하면 coverage를 찾는 비용이 늘어난다.

## Validator Impact

우선은 `promptgate.eval_validation`을 변경하지 않는다. 현재 validator는 다음 expected 필드를 이미 지원한다.

- `status`
- `target_source`
- `target_skill`
- `requires_confirmation`
- `clarification_needed`
- `question_count`
- `refined_prompt_includes`
- `exclusions`
- `output_preferences`
- `goal_includes`
- `solution_candidates`
- `should_not_assume`
- `question_includes`

구현 중 새 case가 이 필드들로 표현되지 않는 경우에만 validator를 최소 확장한다. 확장한다면 새 필드는 fixture 검증용으로만 추가하고 runtime output schema를 바꾸지 않는다.

## Testing

필수 검증 명령은 다음과 같다.

```bash
python3 scripts/validate-evals.py
python3 -m promptgate eval
python3 -m unittest tests.test_validate_evals tests.test_promptgate_eval_runner
```

현재 `python3 -m promptgate eval`은 fixture의 구조 검증과 deterministic guard smoke를 수행한다. 새 case의 expected 값을 실제 provider 출력과 비교하는 scoring harness는 이번 범위가 아니며, 판단 로직 개선 단계에서 별도 설계한다.

전체 회귀 확인이 필요한 경우 다음 명령도 실행한다.

```bash
python3 -m unittest
```

## Acceptance Criteria

- 8개 coverage 유형이 fixture에 반영되어 있다.
- 각 새 case는 명확한 `id`, `input`, `expected`를 가진다.
- 새 case id는 중복되지 않는다.
- validator 변경 없이 표현 가능한 case는 validator를 건드리지 않는다.
- `python3 scripts/validate-evals.py`가 통과한다.
- `python3 -m promptgate eval`이 통과한다.
- 새 coverage가 runtime 판단 로직 변경 없이 fixture validation 기준으로 merge 가능하다.

## 후속 작업

이 coverage 확장 이후 다음 단계는 판단 로직 개선이다. 새 fixture의 expected 기준을 실제 runtime/provider 결과와 비교하는 harness가 필요하면, 별도 계획에서 scoring harness와 matching, clarification, risk policy, guard 로직 조정을 함께 다룬다.
