import tempfile
import unittest
from pathlib import Path

from linux_diag_kit.runner import RetryPolicy, run_command


class TestRunner(unittest.TestCase):
    def test_run_command_success_and_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = run_command(["python3", "-c", "import os; print(os.getcwd())"], cwd=tmp)
            self.assertTrue(res.ok)
            self.assertEqual(res.returncode, 0)
            self.assertEqual(Path(res.stdout.strip()).resolve(), Path(tmp).resolve())

    def test_run_command_dry_run(self):
        res = run_command(["rm", "-rf", "/nonexistent"], dry_run=True)
        self.assertTrue(res.dry_run)
        self.assertTrue(res.ok)
        self.assertEqual(res.attempts, 0)

    def test_run_command_timeout(self):
        res = run_command(["python3", "-c", "import time; time.sleep(2)"], timeout=0.1)
        self.assertFalse(res.ok)
        self.assertTrue(res.timed_out)
        self.assertEqual(res.returncode, 124)

    def test_retry_with_backoff_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "first_attempt_done"
            delays: list[float] = []
            script = (
                "import pathlib, sys; "
                f"p = pathlib.Path({str(marker)!r}); "
                "sys.exit(1 if not p.exists() and (p.write_text('1') or True) else 0)"
            )
            policy = RetryPolicy(
                max_retries=2,
                base_delay_sec=0.5,
                jitter_sec=0.0,
                retry_exit_codes=frozenset({1}),
            )
            res = run_command(["python3", "-c", script], policy=policy, sleep_fn=delays.append)
            self.assertTrue(res.ok)
            self.assertEqual(res.attempts, 2)
            self.assertEqual(delays, [0.5])

    def test_environment_override_and_missing_cwd(self):
        res = run_command(["python3", "-c", "import os; print(os.environ['DIAG_TEST'])"], env={"DIAG_TEST": "ok"})
        self.assertEqual(res.stdout.strip(), "ok")
        with self.assertRaises(FileNotFoundError):
            run_command(["python3", "--version"], cwd="/does/not/exist")


if __name__ == "__main__":
    unittest.main()
