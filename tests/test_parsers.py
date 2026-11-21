from linux_diag_kit.parsers import extract_error_lines


def test_extract_error_lines_normalizes_warning():
    lines = [
        "2026-11-22 INFO Service started",
        "2026-11-22 Warning: high memory usage",
        "2026-11-22 ERROR connection refused",
    ]
    findings = extract_error_lines(lines)
    assert len(findings) == 2
    assert findings[0].line_number == 2
    assert findings[0].severity == "WARN"
    assert findings[1].line_number == 3
    assert findings[1].severity == "ERROR"
