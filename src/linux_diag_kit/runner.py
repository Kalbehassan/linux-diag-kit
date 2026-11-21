"""Safe subprocess execution utilities."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(
    args: Sequence[str],
    *,
    timeout: float = 10.0,
    retries: int = 0,
    retry_delay: float = 0.2,
    dry_run: bool = False,
) -> CommandResult:
    cmd = list(args)
    if not cmd:
        raise ValueError("Command arguments cannot be empty.")

    if dry_run:
        logger.info("Dry-run command: %s", " ".join(cmd))
        return CommandResult(
            command=cmd,
            returncode=0,
            stdout="",
            stderr="",
            duration_sec=0.0,
            dry_run=True,
        )

    attempts = max(0, retries) + 1
    last_result: CommandResult | None = None

    for attempt in range(1, attempts + 1):
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            elapsed = time.monotonic() - start
            last_result = CommandResult(
                command=cmd,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_sec=elapsed,
            )
            if last_result.ok or attempt == attempts:
                return last_result
            logger.warning(
                "Command attempt %d/%d failed with code %d; retrying...",
                attempt,
                attempts,
                proc.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - start
            last_result = CommandResult(
                command=cmd,
                returncode=124,
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=f"Command timed out after {timeout}s",
                duration_sec=elapsed,
            )
            if attempt == attempts:
                return last_result

        if attempt < attempts and retry_delay > 0:
            time.sleep(retry_delay)

    assert last_result is not None
    return last_result
