from pathlib import Path
import pytest

from linux_diag_kit.diagnostics import inspect_log_file


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
