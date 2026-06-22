"""Live (static, no-LLM) prompt linting — the 3 finding types from §4.

- ``stylistic``     (🟡 warning): filler/wordiness, adjacent repetition.
- ``determinism``   (🔵 warning): vague instructions, no explicit output format.
- ``hallucination`` (🔴 error):   asks for external facts without a grounding source.

``lint_template(template)`` returns a list of :class:`Finding`. Coordinates are
1-based; ``end_col`` is exclusive. Findings are capped to keep the editor calm.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_MAX_FINDINGS = 60

# A template is considered "grounded" if it pipes in a source-like variable.
_SOURCE_VAR = re.compile(
    r"\{\{[^}]*\b(context|source|document|reference|data|corpus|passage|evidence|retrieved)\b[^}]*\}\}",
    re.IGNORECASE,
)
_OUTPUT_FORMAT = re.compile(
    r"\b(json|yaml|format|schema|markdown|table|bullet|numbered list|csv)\b|```", re.IGNORECASE
)


@dataclass(frozen=True)
class Finding:
    type: str       # stylistic | determinism | hallucination
    severity: str   # info | warning | error
    line: int       # 1-based
    col: int        # 1-based
    end_col: int    # exclusive
    message: str
    suggestion: str

    def to_dict(self) -> dict:
        return asdict(self)


# (type, severity, pattern, message, suggestion)
_PATTERN_RULES: list[tuple[str, str, re.Pattern, str, str]] = [
    # ── stylistic ──
    ("stylistic", "warning",
     re.compile(r"\b(very|really|quite|just|simply|basically|actually|in order to|"
                r"as previously mentioned|please note that|it is important to note that)\b",
                re.IGNORECASE),
     "Filler/wordiness: “{m}”.",
     "Cut or tighten — filler dilutes the instruction."),
    ("stylistic", "warning",
     re.compile(r"\b(\w{3,})\s+\1\b", re.IGNORECASE),
     "Repeated word: “{m}”.",
     "Remove the duplicate."),
    # ── determinism ──
    ("determinism", "warning",
     re.compile(r"\b(maybe|perhaps|try to|if possible|as needed|as appropriate|"
                r"appropriately|some|several|a few|etc\.?|and so on|or something|"
                r"reasonable|as you see fit)\b", re.IGNORECASE),
     "Vague instruction: “{m}” under-specifies the output.",
     "Replace with a concrete, checkable requirement."),
    ("determinism", "warning",
     re.compile(r"\bbe\s+(creative|concise|brief|detailed|thorough|specific)\b", re.IGNORECASE),
     "Unquantified directive: “{m}”.",
     "Quantify it (e.g. “in ≤3 sentences”, “exactly 5 bullets”)."),
    # ── hallucination (only when ungrounded — see lint_template) ──
    ("hallucination", "error",
     re.compile(r"\b(cite|citations?|according to|references?|sources?|the latest|"
                r"most recent|currently|as of (today|now)|up[- ]to[- ]date|"
                r"exact (number|figure|date)|statistics?|real[- ]time|look up|DOI)\b",
                re.IGNORECASE),
     "Asks for external facts (“{m}”) with no provided source — hallucination risk.",
     "Add a {{context}}/{{source}} block to ground in, and tell the model to say "
     "it doesn't know when the answer isn't there."),
]

_HALLUCINATION_TYPES = {"hallucination"}


def lint_template(template: str) -> list[Finding]:
    """Run all static rules over ``template`` and return findings."""
    if not template:
        return []

    grounded = bool(_SOURCE_VAR.search(template))
    findings: list[Finding] = []
    lines = template.splitlines() or [template]

    for lineno, line in enumerate(lines, start=1):
        for ftype, severity, pattern, msg, sugg in _PATTERN_RULES:
            if ftype in _HALLUCINATION_TYPES and grounded:
                continue  # template provides a source → suppress
            for m in pattern.finditer(line):
                matched = m.group(0)
                findings.append(Finding(
                    type=ftype, severity=severity,
                    line=lineno, col=m.start() + 1, end_col=m.end() + 1,
                    message=msg.format(m=matched.strip()),
                    suggestion=sugg,
                ))
                if len(findings) >= _MAX_FINDINGS:
                    return findings

    # Structural: no explicit output format on a non-trivial prompt.
    if len(template) > 80 and not _OUTPUT_FORMAT.search(template):
        findings.append(Finding(
            type="determinism", severity="warning", line=1, col=1, end_col=2,
            message="No explicit output format specified.",
            suggestion="State the exact output shape (JSON schema, bullet list, table…).",
        ))

    return findings[:_MAX_FINDINGS]
