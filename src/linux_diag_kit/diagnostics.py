"""Log file diagnostics and summary reporting."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from linux_diag_kit.parsers import LogFinding, extract_error_lines


@dataclass(frozen=True)
class LogReport:
    path: Path
    total_lines: int
    counts_by_severity: dict[str, int]
    findings: list[LogFinding]


def inspect_log_file(log_path: str | Path) -> LogReport:
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = extract_error_lines(content)
    counts = dict(Counter(item.severity for item in findings))

    return LogReport(
        path=path,
        total_lines=len(content),
        counts_by_severity=counts,
        findings=findings,
    )
