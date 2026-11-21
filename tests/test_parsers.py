import unittest

from linux_diag_kit.parsers import extract_error_lines, group_failure_clusters, normalize_signature


class TestParsers(unittest.TestCase):
    def test_normalize_signature_masks_volatile_tokens(self):
        raw = (
            "2026-11-22T00:55:10.123Z pid=4821 req_id=abc-99 "
            "Timeout talking to 550e8400-e29b-41d4-a716-446655440000 at 0x7fff1234 after 300ms"
        )
        sig = normalize_signature(raw)
        self.assertIn("<TS>", sig)
        self.assertIn("pid=<N>", sig)
        self.assertIn("req_id=<N>", sig)
        self.assertIn("<UUID>", sig)
        self.assertIn("<HEX>", sig)
        self.assertIn("<N>ms", sig)

    def test_extract_traceback_and_cluster_recurring_errors(self):
        log_lines = [
            "2026-11-22 00:01:00 INFO worker started",
            "2026-11-22 00:01:05 ERROR DB pool exhausted for tenant 101",
            "2026-11-22 00:01:06 ERROR DB pool exhausted for tenant 202",
            "Traceback (most recent call last):",
            '  File "/app/worker.py", line 42, in handle',
            "    raise ValueError('bad payload')",
            "ValueError: bad payload",
        ]
        findings = extract_error_lines(log_lines)
        self.assertEqual(len(findings), 3)
        self.assertIn("ValueError: bad payload", findings[2].full_text)

        clusters = group_failure_clusters(findings)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].count, 2)
        self.assertEqual(clusters[0].signature, "<TS> ERROR DB pool exhausted for tenant <N>")
        self.assertEqual(clusters[0].line_numbers, [2, 3])

    def test_warning_severity_normalization(self):
        findings = extract_error_lines(["WARNING disk slow", "FAILED job", "FATAL process abort"])
        self.assertEqual([item.severity for item in findings], ["WARN", "ERROR", "CRITICAL"])

    def test_extract_error_lines_normalizes_warning(self):
        lines = [
            "2026-11-22 INFO Service started",
            "2026-11-22 Warning: high memory usage",
            "2026-11-22 ERROR connection refused",
        ]
        findings = extract_error_lines(lines)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].line_number, 2)
        self.assertEqual(findings[0].severity, "WARN")
        self.assertEqual(findings[1].line_number, 3)
        self.assertEqual(findings[1].severity, "ERROR")


if __name__ == "__main__":
    unittest.main()
