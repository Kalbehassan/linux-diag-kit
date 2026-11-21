"""Command-line interface for linux-diag-kit."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from linux_diag_kit.diagnostics import inspect_log_file
from linux_diag_kit.runner import run_command


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linux-diag", description="Linux automation & log diagnostics CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_p = subparsers.add_parser("run", help="Run a shell-free command safely")
    run_p.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds")
    run_p.add_argument("--retries", type=int, default=0, help="Number of retries on failure")
    run_p.add_argument("--dry-run", action="store_true", help="Print command without executing")
    run_p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command arguments after '--'")

    logs_p = subparsers.add_parser("inspect-log", help="Scan a log file for warnings and errors")
    logs_p.add_argument("path", help="Path to log file")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_logging(args.verbose)

    if args.subcommand == "run":
        cmd_args = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
        result = run_command(
            cmd_args,
            timeout=args.timeout,
            retries=args.retries,
            dry_run=args.dry_run,
        )
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr + ("\n" if not result.stderr.endswith("\n") else ""))
        return result.returncode

    if args.subcommand == "inspect-log":
        report = inspect_log_file(args.path)
        print(f"File: {report.path} | Lines: {report.total_lines} | Findings: {len(report.findings)}")
        for sev, count in sorted(report.counts_by_severity.items()):
            print(f"  {sev}: {count}")
        for item in report.findings:
            print(f"  L{item.line_number} [{item.severity}] {item.message}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
