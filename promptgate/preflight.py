from __future__ import annotations

from dataclasses import dataclass
import re


BYPASS_PREFIXES = ("/raw", "!그대로", "#no-normalize", "#raw")
VALID_DOMAINS = {"writing", "dev", "design", "resume", "research", "product", "general"}
VALID_NEXT = {"raw-pass-through", "direct", "prompt-normalizer"}

VAGUE_PHRASES = (
    "정리좀",
    "방향만",
    "코드말고",
    "별론데",
    "구조가 안잡힘",
    "맞어?",
    "맞아?",
    "먼 차이야",
    "뭐가 나아",
    "어떻게 해야",
)

CODE_EXCLUSION_PHRASES = ("코드말고", "코드 말고", "구현하지 말고", "구현 말고")
DESIGN_TERMS = ("디자인", "UI", "UX", "컬러", "색", "레이아웃", "타이포", "고급스럽")
DEV_TERMS = ("Redis", "API", "DB", "SQL", "코드", "버그", "에러", "테스트", "서버", "캐시", "세션")
RESUME_TERMS = ("이력서", "resume", "경력기술서", "포트폴리오")
RESEARCH_TERMS = ("조사", "리서치", "검색", "자료", "근거")
PRODUCT_TERMS = ("MVP", "제품", "기능", "유저", "사용자 플로우")
WRITING_TERMS = ("문장", "글", "카피", "메일", "요약", "정리")

SOLUTION_CANDIDATE_PATTERN = re.compile(
    r"(쓰면 되나|로 하면 되나|써도 되나|괜찮나|맞나|나을까|어때)"
)


@dataclass(frozen=True)
class PreflightDecision:
    bypass: bool
    clarity_score: float
    is_vague: bool
    domain_guess: str
    task_type_guess: str
    risk_flags: list[str]
    recommended_next: str
    recommended_skill_hint: str | None
    reason: str

    def as_prompt_payload(self) -> dict[str, object]:
        return {
            "bypass": self.bypass,
            "clarity_score": self.clarity_score,
            "is_vague": self.is_vague,
            "domain_guess": self.domain_guess,
            "task_type_guess": self.task_type_guess,
            "risk_flags": list(self.risk_flags),
            "recommended_next": self.recommended_next,
            "recommended_skill_hint": self.recommended_skill_hint,
            "reason": self.reason,
        }


def analyze_preflight(raw_prompt: str) -> PreflightDecision:
    prompt = raw_prompt.strip()
    lowered = prompt.lower()
    flags: list[str] = []

    if _has_bypass_prefix(prompt):
        return PreflightDecision(
            bypass=True,
            clarity_score=1.0,
            is_vague=False,
            domain_guess=_guess_domain(prompt),
            task_type_guess=_guess_task_type(prompt),
            risk_flags=["bypass_prefix"],
            recommended_next="raw-pass-through",
            recommended_skill_hint=None,
            reason="User requested raw pass-through.",
        )

    clarity = 0.86
    if len(prompt) < 18:
        clarity -= 0.18
        flags.append("short_prompt")

    if any(phrase in prompt for phrase in VAGUE_PHRASES):
        clarity -= 0.24
        flags.append("vague_phrase")

    if any(phrase in prompt for phrase in CODE_EXCLUSION_PHRASES):
        clarity -= 0.08
        flags.append("exclude_code")

    if SOLUTION_CANDIDATE_PATTERN.search(prompt):
        clarity -= 0.16
        flags.append("solution_candidate")

    if "?" in prompt or "？" in prompt or lowered.endswith("나"):
        clarity -= 0.06
        flags.append("question_like")

    clarity = round(max(0.0, min(1.0, clarity)), 2)
    is_vague = clarity < 0.8
    domain = _guess_domain(prompt)
    task_type = _guess_task_type(prompt)
    recommended_next = "prompt-normalizer" if is_vague else "direct"

    return PreflightDecision(
        bypass=False,
        clarity_score=clarity,
        is_vague=is_vague,
        domain_guess=domain,
        task_type_guess=task_type,
        risk_flags=_dedupe(flags),
        recommended_next=recommended_next,
        recommended_skill_hint=_skill_hint(domain, task_type) if is_vague else None,
        reason=_reason(is_vague, flags),
    )


def _has_bypass_prefix(prompt: str) -> bool:
    return any(prompt.startswith(prefix) for prefix in BYPASS_PREFIXES)


def _guess_domain(prompt: str) -> str:
    if _contains_any(prompt, DESIGN_TERMS):
        return "design"
    if _contains_any(prompt, DEV_TERMS):
        return "dev"
    if _contains_any(prompt, RESUME_TERMS):
        return "resume"
    if _contains_any(prompt, RESEARCH_TERMS):
        return "research"
    if _contains_any(prompt, PRODUCT_TERMS):
        return "product"
    if _contains_any(prompt, WRITING_TERMS):
        return "writing"
    return "general"


def _guess_task_type(prompt: str) -> str:
    if any(phrase in prompt for phrase in ("쓰면 되나", "로 하면 되나", "맞나", "뭐가 나아")):
        return "decide"
    if any(phrase in prompt for phrase in ("정리", "요약", "자연스럽게")):
        return "rewrite"
    if any(phrase in prompt for phrase in ("방향", "계획", "플랜")):
        return "plan"
    if any(phrase in prompt for phrase in ("왜", "원인", "안됨", "에러")):
        return "analyze"
    return "respond"


def _skill_hint(domain: str, task_type: str) -> str | None:
    if domain == "design":
        return "design-brief"
    if domain == "dev":
        return "dev-task"
    if domain == "resume":
        return "resume-portfolio"
    if domain == "research":
        return "research-analysis"
    if task_type == "rewrite" or domain == "writing":
        return "writing-rewrite"
    if domain == "product":
        return "brainstorming"
    return None


def _contains_any(prompt: str, terms: tuple[str, ...]) -> bool:
    lowered = prompt.lower()
    return any(term.lower() in lowered for term in terms)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _reason(is_vague: bool, flags: list[str]) -> str:
    if not is_vague:
        return "Prompt is clear enough for direct handling."
    if "solution_candidate" in flags:
        return "User mentions a possible solution as a candidate."
    if "exclude_code" in flags:
        return "User includes an exclusion that should be preserved."
    return "Prompt contains shorthand or implicit intent."
