"""Log parsing, traceback extraction, and failure clustering helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

_LEVEL_PATTERN = re.compile(r"\b(ERROR|WARN|WARNING|CRITICAL|FATAL|FAIL|FAILED)\b", re.IGNORECASE)
_TRACEBACK_START = re.compile(r"^Traceback \(most recent call last\):", re.IGNORECASE)
_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_PID_KV_RE = re.compile(r"\b(pid|tid|worker|req_id|trace_id)=([A-Za-z0-9.*_-]+)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

@dataclass(frozen=True)
class LogFinding:
    line_number: int
    severity: str
    message: str
    traceback: tuple[str, ...] = ()

    @property
    def full_text(self) -> str:
        return self.message if not self.traceback else self.message + "\n" + "\n".join(self.traceback)


@dataclass
class FailureCluster:
    signature: str
    severity: str
    count: int = 0
    line_numbers: list[int] = field(default_factory=list)
    sample_message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "signature": self.signature,
            "severity": self.severity,
            "count": self.count,
            "line_numbers": self.line_numbers,
            "sample_message": self.sample_message,
        }


def _normalize_severity(raw: str) -> str:
    upper = raw.upper()
    if upper == "WARNING":
        return "WARN"
    if upper in {"FAIL", "FAILED"}:
        return "ERROR"
    if upper == "FATAL":
        return "CRITICAL"
    return upper


def normalize_signature(text: str) -> str:
    """Collapse timestamps, IDs, addresses, PIDs, and raw numbers into stable tokens."""
    normalized = _TIMESTAMP_RE.sub("<TS>", text)
    normalized = _UUID_RE.sub("<UUID>", normalized)
    normalized = _HEX_ADDR_RE.sub("<HEX>", normalized)
    normalized = _PID_KV_RE.sub(lambda m: f"{m.group(1).lower()}=<N>", normalized)
    normalized = _NUMBER_RE.sub("<N>", normalized)
    return " ".join(normalized.strip().split())


def extract_error_lines(lines: Iterable[str]) -> list[LogFinding]:
    """Extract warning/error lines and attach complete Python traceback blocks."""
    line_list = [line.rstrip("\r\n") for line in lines]
    findings: list[LogFinding] = []
    i = 0

    while i < len(line_list):
        line = line_list[i]
        if _TRACEBACK_START.match(line.strip()):
            traceback_lines = [line]
            j = i + 1
            while j < len(line_list):
                candidate = line_list[j]
                if candidate.startswith((" ", "\t")):
                    traceback_lines.append(candidate)
                    j += 1
                    continue
                break
            if j < len(line_list) and line_list[j].strip():
                traceback_lines.append(line_list[j])
                j += 1
            exc_summary = traceback_lines[-1].strip()
            findings.append(LogFinding(i + 1, "ERROR", exc_summary, tuple(traceback_lines)))
            i = j
            continue

        match = _LEVEL_PATTERN.search(line)
        if match:
            findings.append(LogFinding(i + 1, _normalize_severity(match.group(1)), line.strip()))
        i += 1

    return findings


def group_failure_clusters(findings: Iterable[LogFinding]) -> list[FailureCluster]:
    """Group findings by normalized signature, ordered by frequency descending."""
    clusters: dict[str, FailureCluster] = {}
    order: list[str] = []

    for finding in findings:
        signature = normalize_signature(finding.message)
        key = f"{finding.severity}:{signature}"
        if key not in clusters:
            clusters[key] = FailureCluster(signature, finding.severity, sample_message=finding.message)
            order.append(key)
        cluster = clusters[key]
        cluster.count += 1
        cluster.line_numbers.append(finding.line_number)

    return sorted(
        (clusters[key] for key in order),
        key=lambda cluster: (-cluster.count, cluster.line_numbers[0] if cluster.line_numbers else 0),
    )
