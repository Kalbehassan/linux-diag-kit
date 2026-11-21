# linux-diag-kit

A modular Python + Linux automation, subprocess orchestration, and failure-triage toolkit built with zero third-party runtime dependencies.

## Architecture

- `src/linux_diag_kit/runner.py` — Subprocess runner with exponential backoff and jitter, timeouts, environment overrides, working-directory enforcement, dry-run mode, and attempt telemetry.
- `src/linux_diag_kit/parsers.py` — Multi-line traceback capture, volatile token normalization, and failure-signature clustering.
- `src/linux_diag_kit/diagnostics.py` — Linux `/proc/meminfo` and `/proc/loadavg` parsing, threshold warnings, log inspection, and JSON-serializable reports.
- `src/linux_diag_kit/cli.py` — `run`, `inspect-log`, `triage`, and `sys-health` workflows with human-readable and JSON output.

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m linux_diag_kit.cli --help
PYTHONPATH=src python3 -m linux_diag_kit.cli sys-health --json
PYTHONPATH=src python3 -m linux_diag_kit.cli run -- python3 -c 'print("ok")'
```
