"""Unit tests for the deep-validation engine (injected scorers, no litellm)."""
from __future__ import annotations

import pytest

from promptgate.quality.deep import RunResult, grade, run_validation


def test_grade_thresholds():
    assert grade(9.0, 0.5) == "green"
    assert grade(8.0, 1.4) == "green"
    assert grade(7.0, 2.0) == "yellow"
    assert grade(6.0, 3.5) == "yellow"
    assert grade(5.9, 1.0) == "red"      # comprehension too low
    assert grade(9.0, 4.0) == "red"      # too much hallucination


def _gen_const(answer="ANSWER", latency=10):
    return lambda case: (answer, latency)


def _judge_const(comp=9.0, hall=0.5):
    return lambda q, a: (comp, hall)


def test_deterministic_answers_score_100():
    cases = [{"question": "q1"}, {"question": "q2"}]
    r = run_validation(cases, _gen_const(), _judge_const(), repeats=4)
    assert r.determinism == 100.0
    assert r.comprehension == 9.0 and r.hallucination == 0.5
    assert r.n_cases == 2 and r.color == "green"
    assert r.latency_ms == 10


def test_unstable_answers_lower_determinism():
    seq = iter(["a", "a", "b", "c"])  # 4 repeats, modal 'a' appears 2/4 = 50%
    def gen(case):
        return next(seq), 5
    r = run_validation([{"question": "q"}], gen, _judge_const(), repeats=4)
    assert r.determinism == 50.0


def test_averages_across_cases():
    judges = iter([(8.0, 1.0), (6.0, 3.0)])
    def judge(q, a):
        return next(judges)
    r = run_validation([{"question": "q1"}, {"question": "q2"}], _gen_const(), judge, repeats=1)
    assert r.comprehension == 7.0
    assert r.hallucination == 2.0


def test_empty_cases_raises():
    with pytest.raises(ValueError):
        run_validation([], _gen_const(), _judge_const())
    with pytest.raises(ValueError):
        run_validation([{"question": "   "}], _gen_const(), _judge_const())


def test_to_dict_shape():
    r = run_validation([{"question": "q"}], _gen_const(), _judge_const(), repeats=1)
    d = r.to_dict()
    assert {"determinism", "comprehension", "hallucination", "latency_ms",
            "n_cases", "color", "cases"} <= set(d)
    assert d["cases"][0]["question"] == "q"
