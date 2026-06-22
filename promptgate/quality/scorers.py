"""Real LLM-backed scorers for deep validation.

Build the ``generate_fn`` / ``judge_fn`` that :func:`promptgate.quality.deep.run_validation`
consumes. These import litellm/runner lazily so the rest of the quality package
stays importable without the ``litellm`` extra; tests inject fakes instead.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_JUDGE_SYSTEM = (
    "You are a strict evaluator of LLM answers. You output only JSON."
)


def build_generate_fn(prompt_id: str, model_id: str, db_path: str | Path):
    """generate_fn(case) -> (answer_text, latency_ms). Needs the litellm extra."""
    from promptgate.runner import run as pg_run  # lazy: pulls litellm

    def generate(case: dict) -> tuple[str, int]:
        payload = case.get("payload") or {}
        t0 = time.perf_counter()
        result = pg_run(
            prompt_id, payload, model_id, db_path=db_path,
            max_retries=1, user_message=case.get("question"),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        answer = result.data if result.data is not None else result.raw_output
        if not isinstance(answer, str):
            answer = json.dumps(answer, ensure_ascii=False, sort_keys=True)
        return answer, latency_ms

    return generate


def build_judge_fn(model_id: str):
    """judge_fn(question, answer) -> (comprehension_0_10, hallucination_0_10)."""
    import litellm  # lazy

    def judge(question: str, answer: str) -> tuple[float, float]:
        user = (
            f"Question:\n{question}\n\nAnswer:\n{answer}\n\n"
            "Rate the answer and return ONLY JSON of the form "
            '{"comprehension": <0-10, how well the answer understood and addressed '
            'the question>, "hallucination": <0-10, amount of unsupported or fabricated '
            'content, 0 = fully grounded>}.'
        )
        resp = litellm.completion(model=model_id, messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ])
        text = resp.choices[0].message.content
        return _parse_scores(text)

    return judge


def _parse_scores(text: str) -> tuple[float, float]:
    """Extract {comprehension, hallucination} from a judge response; clamp 0-10."""
    comprehension = hallucination = 0.0
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            comprehension = float(data.get("comprehension", 0) or 0)
            hallucination = float(data.get("hallucination", 0) or 0)
        except (ValueError, TypeError):
            pass
    clamp = lambda x: max(0.0, min(10.0, x))
    return clamp(comprehension), clamp(hallucination)
