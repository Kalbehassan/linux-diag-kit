from pathlib import Path
import json
import tempfile
import unittest
import pytest

from linux_diag_kit.cli import main
from linux_diag_kit.diagnostics import collect_system_health, inspect_log_file, triage_log_file


def test_inspect_log_file(tmp_path: Path):
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "boot ok\nERROR disk full on /var\nWARN retry queue near capacity\n",
        encoding="utf-8",
    )
    report = inspect_log_file(log_file)
    assert report.total_lines == 3
    assert report.counts_by_severity == {"ERROR": 1, "WARN": 1}
    assert len(report.findings) == 2


def test_inspect_log_file_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        inspect_log_file(tmp_path / "missing.log")


class TestDiagnostics(unittest.TestCase):
    def test_triage_log_file_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "service.log"
            log_path.write_text("\n".join([
                "2026-11-22 01:00:00 INFO boot",
                "2026-11-22 01:00:01 WARNING disk latency 120ms",
                "2026-11-22 01:00:02 WARNING disk latency 240ms",
                "2026-11-22 01:00:03 CRITICAL out of memory",
            ]) + "\n", encoding="utf-8")
            report = triage_log_file(log_path)
            self.assertEqual(report.total_lines, 4)
            self.assertEqual(report.total_findings, 3)
            self.assertEqual(report.clusters[0].severity, "WARN")
            self.assertEqual(report.clusters[0].count, 2)

            with self.assertRaises(FileNotFoundError):
                triage_log_file(Path(tmp) / "does_not_exist.log")

    def test_collect_system_health_from_proc_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            meminfo = Path(tmp) / "meminfo"
            loadavg = Path(tmp) / "loadavg"
            meminfo.write_text("MemTotal:       16000000 kB\nMemAvailable:    1600000 kB\n", encoding="utf-8")
            loadavg.write_text("4.25 3.10 2.50 2/400 12345\n", encoding="utf-8")

            health = collect_system_health(
                proc_meminfo=meminfo,
                proc_loadavg=loadavg,
                mem_warn_pct=85.0,
                load_1m_warn=4.0,
            )
            self.assertAlmostEqual(health.mem_used_pct or 0.0, 90.0, places=1)
            self.assertIn("High memory usage", " ".join(health.warnings))
            self.assertIn("High 1m load average", " ".join(health.warnings))

    def test_cli_sys_health_json_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            meminfo = Path(tmp) / "meminfo"
            loadavg = Path(tmp) / "loadavg"
            meminfo.write_text("MemTotal: 100000 kB\nMemAvailable: 10000 kB\n", encoding="utf-8")
            loadavg.write_text("5.0 2.0 1.0 1/100 42\n", encoding="utf-8")
            rc = main([
                "sys-health", "--json", "--meminfo", str(meminfo), "--loadavg", str(loadavg),
                "--mem-warn-pct", "80", "--load-warn", "4",
            ])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
