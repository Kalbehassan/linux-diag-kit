"""Command-line interface for linux-diag-kit."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Sequence

from linux_diag_kit.diagnostics import collect_system_health, inspect_log_file, triage_log_file
from linux_diag_kit.runner import RetryPolicy, run_command


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linux-diag", description="Linux automation & failure triage CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_p = subparsers.add_parser("run", help="Run a shell-free command safely")
    run_p.add_argument("--cwd", default=None, help="Working directory")
    run_p.add_argument("--timeout", type=float, default=10.0, help="Per-attempt timeout in seconds")
    run_p.add_argument("--retries", type=int, default=0, help="Max retry attempts")
    run_p.add_argument("--base-delay", type=float, default=0.2, help="Base backoff delay")
    run_p.add_argument("--dry-run", action="store_true", help="Print command without executing")
    run_p.add_argument("--json", action="store_true", dest="run_json", help=argparse.SUPPRESS)
    run_p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command arguments after '--'")

    logs_p = subparsers.add_parser("inspect-log", help="Scan a log file for findings")
    logs_p.add_argument("path", help="Path to log file")
    logs_p.add_argument("--json", action="store_true", dest="logs_json", help=argparse.SUPPRESS)

    triage_p = subparsers.add_parser("triage", help="Cluster recurring failure signatures")
    triage_p.add_argument("path", help="Path to log file")
    triage_p.add_argument("--top", type=int, default=10, help="Max top failure clusters")
    triage_p.add_argument("--json", action="store_true", dest="triage_json", help=argparse.SUPPRESS)

    health_p = subparsers.add_parser("sys-health", help="Inspect /proc memory, load, and disk")
    health_p.add_argument("--meminfo", default="/proc/meminfo", help="Path to meminfo")
    health_p.add_argument("--loadavg", default="/proc/loadavg", help="Path to loadavg")
    health_p.add_argument("--mem-warn-pct", type=float, default=85.0)
    health_p.add_argument("--load-warn", type=float, default=None)
    health_p.add_argument("--disk-warn-pct", type=float, default=90.0)
    health_p.add_argument("--json", action="store_true", dest="health_json", help=argparse.SUPPRESS)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_logging(args.verbose)

    def json_output(sub_value: bool, payload: dict[str, object]) -> bool:
        if args.as_json or sub_value:
            print(json.dumps(payload, indent=2))
            return True
        return False

    if args.subcommand == "run":
        cmd_args = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
        policy = RetryPolicy(max_retries=args.retries, base_delay_sec=args.base_delay)
        try:
            result = run_command(cmd_args, cwd=args.cwd, timeout=args.timeout, policy=policy, dry_run=args.dry_run)
        except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        if json_output(args.run_json, result.to_dict()) is False:
            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr + ("" if result.stderr.endswith("\n") else "\n"))
        return result.returncode

    if args.subcommand == "inspect-log":
        try:
            report = inspect_log_file(args.path)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 1
        if not json_output(args.logs_json, {
            "path": str(report.path),
            "total_lines": report.total_lines,
            "counts_by_severity": report.counts_by_severity,
            "findings": [
                {"line_number": finding.line_number, "severity": finding.severity,
                 "message": finding.message, "traceback": list(finding.traceback)}
                for finding in report.findings
            ],
        }):
            print(f"File: {report.path} | Lines: {report.total_lines} | Findings: {len(report.findings)}")
            for severity, count in sorted(report.counts_by_severity.items()):
                print(f"  {severity}: {count}")
            for finding in report.findings:
                print(f"  L{finding.line_number} [{finding.severity}] {finding.message}")
        return 0

    if args.subcommand == "triage":
        try:
            triage = triage_log_file(args.path)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 1
        top_clusters = triage.clusters[:max(1, args.top)]
        if not json_output(args.triage_json, {**triage.to_dict(), "clusters": [cluster.to_dict() for cluster in top_clusters]}):
            print(f"Triage: {triage.path} | Lines: {triage.total_lines} | Findings: {triage.total_findings} | Unique Clusters: {len(triage.clusters)}")
            for index, cluster in enumerate(top_clusters, start=1):
                lines_preview = ",".join(str(number) for number in cluster.line_numbers[:5])
                print(f"  #{index} [{cluster.severity}] x{cluster.count} (lines: {lines_preview}) -> {cluster.signature}")
        return 0

    if args.subcommand == "sys-health":
        health = collect_system_health(
            proc_meminfo=args.meminfo,
            proc_loadavg=args.loadavg,
            mem_warn_pct=args.mem_warn_pct,
            load_1m_warn=args.load_warn,
            disk_warn_pct=args.disk_warn_pct,
        )
        if not json_output(args.health_json, health.to_dict()):
            print(f"Load (1m/5m/15m): {health.load_1m} / {health.load_5m} / {health.load_15m} | Mem Used %: {health.mem_used_pct}")
            for warning in health.warnings:
                print(f"  WARNING: {warning}")
        return 1 if health.warnings else 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
