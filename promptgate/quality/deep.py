"""Deep (LLM-backed) prompt validation — P3.

Runs a prompt over a small test set, repeated per case, and scores:
- ``determinism`` (0-100): answer stability across repeats (modal-answer share)
- ``comprehension`` (0-10, higher better): LLM-judge rating
- ``hallucination`` (0-10, lower better): LLM-judge rating
- ``latency_ms``: mean per-generation latency

The LLM calls are **injected** (``generate_fn`` / ``judge_fn``) so the engine is
unit-testable without litellm; the API layer supplies real implementations
(see :mod:`promptgate.quality.scorers`).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Callable

# generate_fn(case_dict) -> (answer_text, latency_ms)
GenerateFn = Callable[[dict], "tuple[str, int]"]
# judge_fn(question, answer) -> (comprehension_0_10, hallucination_0_10)
JudgeFn = Callable[[str, str], "tuple[float, float]"]


def grade(comprehension: float, hallucination: float) -> str:
    """Color grade per docs §8.2."""
    if comprehension >= 8.0 and hallucination < 1.5:
        return "green"
    if comprehension >= 6.0 and hallucination <= 3.5:
        return "yellow"
    return "red"


@dataclass
class CaseResult:
    question: str
    answer: str
    score: float            # comprehension for this case (0-10)
    hallucination: float    # 0-10
    determinism: float      # per-case stability 0-100
    flagged_block: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunResult:
    determinism: float
    comprehension: float
    hallucination: float
    latency_ms: int
    n_cases: int
    color: str
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def run_validation(
    cases: list[dict],
    generate_fn: GenerateFn,
    judge_fn: JudgeFn,
    repeats: int = 3,
) -> RunResult:
    """Validate a prompt over ``cases`` (each ``{"question", "payload"?}``).

    Each case is generated ``repeats`` times to measure determinism; the modal
    answer is judged once for comprehension/hallucination.
    """
    cases = [c for c in cases if (c.get("question") or "").strip()]
    if not cases:
        raise ValueError("At least one test case with a question is required")
    repeats = max(1, repeats)

    case_results: list[CaseResult] = []
    latencies: list[int] = []

    for case in cases:
        answers: list[str] = []
        for _ in range(repeats):
            answer, latency = generate_fn(case)
            answers.append(answer if answer is not None else "")
            latencies.append(int(latency))

        normalized = [a.strip() for a in answers]
        modal, count = Counter(normalized).most_common(1)[0]
        determinism = 100.0 * count / len(normalized)
        representative = answers[normalized.index(modal)]

        comprehension, hallucination = judge_fn(case["question"], representative)
        case_results.append(CaseResult(
            question=case["question"], answer=representative,
            score=float(comprehension), hallucination=float(hallucination),
            determinism=round(determinism, 1),
        ))

    n = len(case_results)
    determinism = round(sum(c.determinism for c in case_results) / n, 1)
    comprehension = round(sum(c.score for c in case_results) / n, 2)
    hallucination = round(sum(c.hallucination for c in case_results) / n, 2)
    latency_ms = int(sum(latencies) / len(latencies)) if latencies else 0

    return RunResult(
        determinism=determinism, comprehension=comprehension,
        hallucination=hallucination, latency_ms=latency_ms,
        n_cases=n, color=grade(comprehension, hallucination), cases=case_results,
    )
