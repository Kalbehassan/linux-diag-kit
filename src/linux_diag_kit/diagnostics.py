"""Log triage and Linux /proc system health diagnostics."""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from linux_diag_kit.parsers import FailureCluster, LogFinding, extract_error_lines, group_failure_clusters


@dataclass(frozen=True)
class LogReport:
    path: Path
    total_lines: int
    counts_by_severity: dict[str, int]
    findings: list[LogFinding]


@dataclass(frozen=True)
class TriageReport:
    path: Path
    total_lines: int
    total_findings: int
    counts_by_severity: dict[str, int]
    clusters: list[FailureCluster]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "total_lines": self.total_lines,
            "total_findings": self.total_findings,
            "counts_by_severity": self.counts_by_severity,
            "clusters": [cluster.to_dict() for cluster in self.clusters],
        }


@dataclass(frozen=True)
class SystemHealthReport:
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    mem_total_kb: int | None
    mem_available_kb: int | None
    mem_used_pct: float | None
    warnings: list[str]
    disk_total_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_free_bytes: int | None = None
    disk_used_pct: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "load_average": {"1m": self.load_1m, "5m": self.load_5m, "15m": self.load_15m},
            "memory_kb": {
                "total": self.mem_total_kb,
                "available": self.mem_available_kb,
                "used_pct": round(self.mem_used_pct, 2) if self.mem_used_pct is not None else None,
            },
            "disk_usage": {
                "total_bytes": self.disk_total_bytes,
                "used_bytes": self.disk_used_bytes,
                "free_bytes": self.disk_free_bytes,
                "used_pct": round(self.disk_used_pct, 2) if self.disk_used_pct is not None else None,
            },
            "warnings": self.warnings,
        }


def inspect_log_file(log_path: str | Path) -> LogReport:
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = extract_error_lines(content)
    counts = dict(Counter(item.severity for item in findings))
    return LogReport(path, len(content), counts, findings)


def triage_log_file(log_path: str | Path) -> TriageReport:
    report = inspect_log_file(log_path)
    clusters = group_failure_clusters(report.findings)
    return TriageReport(report.path, report.total_lines, len(report.findings), report.counts_by_severity, clusters)


def parse_loadavg(lines: Iterable[str]) -> tuple[float | None, float | None, float | None]:
    first = next((line.strip() for line in lines if line.strip()), "")
    parts = first.split()
    if len(parts) < 3:
        return None, None, None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None, None, None


def parse_meminfo(lines: Iterable[str]) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        tokens = rest.strip().split()
        if tokens and tokens[0].isdigit():
            values[key.strip()] = int(tokens[0])
    return values


def collect_system_health(
    *,
    proc_meminfo: str | Path = "/proc/meminfo",
    proc_loadavg: str | Path = "/proc/loadavg",
    mem_warn_pct: float = 85.0,
    load_1m_warn: float | None = None,
    disk_warn_pct: float = 90.0,
    disk_path: str | Path = "/",
) -> SystemHealthReport:
    """Collect Linux /proc memory/load metrics and root-disk usage."""
    warnings: list[str] = []

    load_1m = load_5m = load_15m = None
    load_path = Path(proc_loadavg)
    if load_path.exists():
        load_1m, load_5m, load_15m = parse_loadavg(
            load_path.read_text(encoding="utf-8", errors="replace").splitlines()
        )

    mem_total_kb = mem_available_kb = None
    mem_used_pct: float | None = None
    mem_path = Path(proc_meminfo)
    if mem_path.exists():
        info = parse_meminfo(mem_path.read_text(encoding="utf-8", errors="replace").splitlines())
        mem_total_kb = info.get("MemTotal")
        mem_available_kb = info.get("MemAvailable")
        if mem_total_kb and mem_total_kb > 0 and mem_available_kb is not None:
            used_kb = max(0, mem_total_kb - mem_available_kb)
            mem_used_pct = (used_kb / mem_total_kb) * 100.0
            if mem_used_pct >= mem_warn_pct:
                warnings.append(f"High memory usage: {mem_used_pct:.1f}% (>= {mem_warn_pct:.1f}%)")

    if load_1m is not None and load_1m_warn is not None and load_1m >= load_1m_warn:
        warnings.append(f"High 1m load average: {load_1m:.2f} (>= {load_1m_warn:.2f})")

    disk_total = disk_used = disk_free = None
    disk_used_pct: float | None = None
    try:
        usage = shutil.disk_usage(str(disk_path))
        disk_total, disk_used, disk_free = usage.total, usage.used, usage.free
        disk_used_pct = (disk_used / disk_total * 100.0) if disk_total else None
        if disk_used_pct is not None and disk_used_pct >= disk_warn_pct:
            warnings.append(f"High disk usage: {disk_used_pct:.1f}% (>= {disk_warn_pct:.1f}%)")
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        pass

    return SystemHealthReport(
        load_1m, load_5m, load_15m,
        mem_total_kb, mem_available_kb, mem_used_pct, warnings,
        disk_total, disk_used, disk_free, disk_used_pct,
    )
