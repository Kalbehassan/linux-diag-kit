"""Resilient subprocess execution with backoff, timeouts, and dry-run support."""

from __future__ import annotations

import logging
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    base_delay_sec: float = 0.2
    max_delay_sec: float = 5.0
    backoff_factor: float = 2.0
    jitter_sec: float = 0.05
    retry_exit_codes: frozenset[int] = field(default_factory=lambda: frozenset({1, 75, 124}))

    def compute_delay(self, attempt_index: int) -> float:
        raw = self.base_delay_sec * (self.backoff_factor ** max(0, attempt_index - 1))
        capped = min(self.max_delay_sec, raw)
        jitter = random.uniform(0.0, self.jitter_sec) if self.jitter_sec > 0 else 0.0
        return max(0.0, capped + jitter)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float
    attempts: int = 1
    timed_out: bool = False
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_sec": round(self.duration_sec, 4),
            "attempts": self.attempts,
            "timed_out": self.timed_out,
            "dry_run": self.dry_run,
        }


def run_command(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    policy: RetryPolicy | None = None,
    dry_run: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    retries: int | None = None,
) -> CommandResult:
    """Execute a command safely without a shell, with optional retries."""
    cmd = list(args)
    if not cmd:
        raise ValueError("Command arguments cannot be empty.")
    if timeout <= 0:
        raise ValueError("Timeout must be greater than 0.")

    resolved_cwd = Path(cwd) if cwd is not None else None
    if resolved_cwd is not None:
        if not resolved_cwd.exists():
            raise FileNotFoundError(f"Working directory does not exist: {resolved_cwd}")
        if not resolved_cwd.is_dir():
            raise NotADirectoryError(f"Working directory is not a directory: {resolved_cwd}")

    retry_policy = policy or RetryPolicy()
    if retries is not None:
        retry_policy = RetryPolicy(
            max_retries=max(0, retries),
            base_delay_sec=retry_policy.base_delay_sec,
            max_delay_sec=retry_policy.max_delay_sec,
            backoff_factor=retry_policy.backoff_factor,
            jitter_sec=retry_policy.jitter_sec,
            retry_exit_codes=retry_policy.retry_exit_codes,
        )
    if retry_policy.max_retries < 0:
        raise ValueError("max_retries cannot be negative.")

    if dry_run:
        logger.info("Dry-run command: %s (cwd=%s)", " ".join(cmd), resolved_cwd or os.getcwd())
        return CommandResult(cmd, 0, "", "", 0.0, attempts=0, dry_run=True)

    merged_env = None
    if env is not None:
        merged_env = os.environ.copy()
        merged_env.update(env)

    overall_start = time.monotonic()
    total_attempts = retry_policy.max_retries + 1
    last_result: CommandResult | None = None

    for attempt in range(1, total_attempts + 1):
        attempt_start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(resolved_cwd) if resolved_cwd else None,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            elapsed = time.monotonic() - attempt_start
            last_result = CommandResult(
                cmd, proc.returncode, proc.stdout, proc.stderr, elapsed,
                attempts=attempt, timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - attempt_start
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            timeout_msg = f"Command timed out after {timeout}s"
            last_result = CommandResult(
                cmd, 124, stdout,
                f"{stderr}\n{timeout_msg}".strip() if stderr else timeout_msg,
                elapsed, attempts=attempt, timed_out=True,
            )

        if (
            last_result.ok
            or attempt >= total_attempts
            or last_result.returncode not in retry_policy.retry_exit_codes
        ):
            return CommandResult(
                last_result.command,
                last_result.returncode,
                last_result.stdout,
                last_result.stderr,
                time.monotonic() - overall_start,
                attempts=attempt,
                timed_out=last_result.timed_out,
            )

        delay = retry_policy.compute_delay(attempt)
        logger.warning("Attempt %d/%d failed (rc=%d); backing off %.3fs", attempt, total_attempts, last_result.returncode, delay)
        sleep_fn(delay)

    assert last_result is not None
    return last_result
