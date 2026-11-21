"""Log and output parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_LEVEL_PATTERN = re.compile(r"\b(ERROR|WARN|WARNING|CRITICAL|FATAL|FAIL|FAILED)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LogFinding:
    line_number: int
    severity: str
    message: str


def extract_error_lines(lines: Iterable[str]) -> list[LogFinding]:
    findings: list[LogFinding] = []
    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        match = _LEVEL_PATTERN.search(line)
        if match:
            severity = match.group(1).upper()
            if severity == "WARNING":
                severity = "WARN"
            findings.append(LogFinding(line_number=idx, severity=severity, message=line.strip()))
    return findings
