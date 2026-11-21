"""Linux automation, subprocess orchestration, and failure diagnostics toolkit."""

from linux_diag_kit.diagnostics import SystemHealthReport, TriageReport, collect_system_health, triage_log_file
from linux_diag_kit.parsers import FailureCluster, LogFinding, extract_error_lines, group_failure_clusters, normalize_signature
from linux_diag_kit.runner import CommandResult, RetryPolicy, run_command

__all__ = [
    "__version__",
    "CommandResult",
    "RetryPolicy",
    "run_command",
    "LogFinding",
    "FailureCluster",
    "extract_error_lines",
    "normalize_signature",
    "group_failure_clusters",
    "SystemHealthReport",
    "TriageReport",
    "collect_system_health",
    "triage_log_file",
]

__version__ = "0.2.0"
