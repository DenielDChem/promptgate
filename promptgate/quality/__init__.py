"""Prompt quality analysis.

P2 ships the *live* layer: fast, local, static checks surfaced in the editor as
squiggles (no LLM call). The *deep* LLM-backed validator (determinism /
comprehension / hallucination scoring over a test set) is P3.
"""
from __future__ import annotations

from promptgate.quality.live import Finding, lint_template

__all__ = ["Finding", "lint_template"]
