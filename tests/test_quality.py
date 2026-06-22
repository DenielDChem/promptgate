"""Tests for the static 3-type live lint engine (P2)."""
from __future__ import annotations

from promptgate.quality.live import lint_template


def _types(findings):
    return {f.type for f in findings}


def test_clean_prompt_minimal_findings():
    findings = lint_template("Summarize the input as JSON: {{ text }}")
    # well-specified + has output format + no fact request → no findings
    assert findings == []


def test_stylistic_filler_flagged():
    f = lint_template("Please note that you should just answer in JSON.")
    assert "stylistic" in _types(f)
    assert any("just" in x.message or "Please note that" in x.message for x in f)


def test_adjacent_repetition_flagged():
    f = lint_template("Return the the answer as JSON.")
    assert any(x.type == "stylistic" and "Repeated" in x.message for x in f)


def test_determinism_vague_flagged():
    f = lint_template("Maybe summarize some of the key points etc. as JSON.")
    assert "determinism" in _types(f)


def test_missing_output_format_flagged():
    long_no_format = "You are an assistant. " * 6 + "Answer the user's question thoroughly."
    f = lint_template(long_no_format)
    assert any(x.type == "determinism" and "output format" in x.message for x in f)


def test_hallucination_flagged_when_ungrounded():
    f = lint_template("Cite the latest statistics on inflation as JSON.")
    assert "hallucination" in _types(f)


def test_hallucination_suppressed_when_grounded():
    f = lint_template("Using only {{ context }}, cite the latest statistics. Answer as JSON.")
    assert "hallucination" not in _types(f)


def test_coordinates_are_1_based():
    f = lint_template("answer\nplease note that x")
    fillers = [x for x in f if x.type == "stylistic"]
    assert fillers and fillers[0].line == 2 and fillers[0].col >= 1


def test_empty_template():
    assert lint_template("") == []
