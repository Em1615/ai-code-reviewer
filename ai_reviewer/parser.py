"""Parses raw LLM output (per the format enforced in prompts.SYSTEM_PROMPT)
into structured Issue objects.

Expected line format:
    [SEVERITY] FILE:LINE — CATEGORY: description

The regex is deliberately lenient about the dash character (—, -, --) and
surrounding whitespace, since models sometimes substitute a plain hyphen
for an em dash even when instructed otherwise. Lines that don't match are
dropped rather than crashing the pipeline — a malformed line is not worth
failing the whole CI job over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
_VALID_CATEGORIES = {
    "BUG",
    "LOGIC",
    "SECURITY",
    "PERFORMANCE",
    "RELIABILITY",
    "MEMORY",
    "CONCURRENCY",
    "COMPATIBILITY",
    "DEPRECATION",
    "TYPE",
}

# [SEVERITY] FILE:LINE <dash> CATEGORY: description
_ISSUE_RE = re.compile(
    r"^\[(?P<severity>[A-Z]+)\]\s*"
    r"(?P<file>[^:]+):(?P<line>\d+)\s*"
    r"[—\-–]{1,2}\s*"
    r"(?P<category>[A-Z]+):\s*"
    r"(?P<description>.+)$"
)

NO_ISSUES_MARKER = "NO ISSUES FOUND"


@dataclass
class Issue:
    severity: str
    file: str
    line: int
    category: str
    description: str

    def format_comment(self) -> str:
        return f"**[{self.severity}] {self.category}**: {self.description}"


def parse_issues(raw_output: str) -> list[Issue]:
    """Parse model output into a list of Issue objects.

    Returns an empty list both when the model says NO ISSUES FOUND and
    when nothing parseable is found at all.
    """
    text = raw_output.strip()
    if not text or text == NO_ISSUES_MARKER:
        return []

    issues: list[Issue] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        match = _ISSUE_RE.match(line)
        if not match:
            continue

        severity = match.group("severity").upper()
        category = match.group("category").upper()

        if severity not in _VALID_SEVERITIES:
            continue
        if category not in _VALID_CATEGORIES:
            continue

        issues.append(
            Issue(
                severity=severity,
                file=match.group("file").strip(),
                line=int(match.group("line")),
                category=category,
                description=match.group("description").strip(),
            )
        )

    return issues