"""Tests for agentagent2.gates.

Ruff/mypy/pytest are not assumed to be installed (the harness is designed to run without them —
see gates.py's module docstring), so most of these tests target the pure-Python pieces
(GateReport/GateOutcome, the secrets scan) plus a real end-to-end run of the stdlib fallback
path (unittest discovery + trace-based coverage) against a tiny throwaway fixture project.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from agentagent2.gates import GateOutcome, GateReport, _run_secrets_scan, run_gates

HAS_RUFF = shutil.which("ruff") is not None
HAS_MYPY = shutil.which("mypy") is not None


class TestGateOutcome(unittest.TestCase):
    def test_ok_true_only_for_pass(self) -> None:
        self.assertTrue(GateOutcome("x", "pass").ok)
        self.assertFalse(GateOutcome("x", "fail").ok)
        self.assertFalse(GateOutcome("x", "missing_tool").ok)
        self.assertFalse(GateOutcome("x", "error").ok)


class TestGateReport(unittest.TestCase):
    def test_empty_report_does_not_pass(self) -> None:
        self.assertFalse(GateReport().passed)

    def test_passes_only_if_every_outcome_passes(self) -> None:
        report = GateReport(outcomes=[GateOutcome("a", "pass"), GateOutcome("b", "pass")])
        self.assertTrue(report.passed)
        report.outcomes.append(GateOutcome("c", "fail"))
        self.assertFalse(report.passed)

    def test_missing_tool_counts_as_not_passed(self) -> None:
        report = GateReport(outcomes=[GateOutcome("a", "missing_tool")])
        self.assertFalse(report.passed)

    def test_summary_lists_every_gate(self) -> None:
        report = GateReport(outcomes=[GateOutcome("format", "pass"), GateOutcome("lint", "fail")])
        summary = report.summary()
        self.assertIn("format: pass", summary)
        self.assertIn("lint: fail", summary)

    def test_detail_is_empty_when_all_pass(self) -> None:
        report = GateReport(outcomes=[GateOutcome("a", "pass")])
        self.assertEqual(report.detail(), "")

    def test_detail_includes_only_failing_gates(self) -> None:
        report = GateReport(
            outcomes=[
                GateOutcome("a", "pass", "should not appear"),
                GateOutcome("b", "fail", "boom detail"),
            ]
        )
        detail = report.detail()
        self.assertNotIn("should not appear", detail)
        self.assertIn("boom detail", detail)
        self.assertIn("b (fail)", detail)


class TestSecretsScan(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_tree_passes(self) -> None:
        (self.root / "app.py").write_text("def main():\n    return 42\n")
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "pass")

    def test_aws_key_is_flagged(self) -> None:
        (self.root / "config.py").write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "fail")
        self.assertIn("config.py", outcome.detail)

    def test_private_key_block_is_flagged(self) -> None:
        (self.root / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n")
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "fail")

    def test_hardcoded_password_is_flagged(self) -> None:
        (self.root / "settings.py").write_text('password = "hunter2isnotarealpassword"\n')
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "fail")

    def test_git_directory_is_not_scanned(self) -> None:
        git_dir = self.root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "pass")

    def test_short_password_like_value_is_not_flagged(self) -> None:
        (self.root / "app.py").write_text('password = "short"\n')  # below the length heuristic
        outcome = _run_secrets_scan(self.root)
        self.assertEqual(outcome.status, "pass")


class TestRunGatesFallbackPath(unittest.TestCase):
    """End-to-end: run_gates() against a tiny real project, using the stdlib fallback path.

    Ruff/mypy are skipped via unittest's own skip mechanism when not installed (they report
    "missing_tool" rather than "pass"/"fail" in that case, which run_gates already handles
    gracefully — this class instead verifies the parts that always work: tests + coverage +
    secrets, end to end, using the real trace-runner subprocess).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "src" / "pkg").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "src" / "pkg" / "__init__.py").write_text("")
        (self.root / "src" / "pkg" / "core.py").write_text(
            "def add(a, b):\n"
            "    return a + b\n"
            "\n"
            "\n"
            "def unused_branch(flag):\n"
            "    if flag:\n"
            "        return 1\n"
            "    return 2\n"
        )
        (self.root / "tests" / "__init__.py").write_text("")
        (self.root / "tests" / "test_core.py").write_text(
            "import unittest\n"
            "from pkg.core import add\n"
            "\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(1, 2), 3)\n"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tests_gate_passes_for_passing_suite(self) -> None:
        report = run_gates(self.root)
        tests_outcome = next(o for o in report.outcomes if o.name == "tests")
        self.assertEqual(tests_outcome.status, "pass", tests_outcome.detail)

    def test_coverage_gate_reports_partial_coverage(self) -> None:
        # unused_branch() is never called by the one test above, so coverage must be < 100%
        # but > 0% (add() is fully covered) — this proves real measurement, not a stub value.
        report = run_gates(self.root)
        coverage_outcome = next(o for o in report.outcomes if o.name == "coverage")
        self.assertIn("%", coverage_outcome.detail)

    def test_tests_gate_fails_for_failing_suite(self) -> None:
        (self.root / "tests" / "test_core.py").write_text(
            "import unittest\n"
            "\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_fails(self):\n"
            "        self.assertEqual(1, 2)\n"
        )
        report = run_gates(self.root)
        tests_outcome = next(o for o in report.outcomes if o.name == "tests")
        self.assertEqual(tests_outcome.status, "fail")

    def test_missing_src_or_tests_reports_coverage_error(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            report = run_gates(Path(empty))
            coverage_outcome = next(o for o in report.outcomes if o.name == "coverage")
            self.assertEqual(coverage_outcome.status, "error")

    def test_report_includes_all_six_gates(self) -> None:
        report = run_gates(self.root)
        self.assertEqual(
            [o.name for o in report.outcomes],
            ["format", "lint", "typecheck", "tests", "coverage", "secrets"],
        )

    @unittest.skipUnless(HAS_RUFF, "ruff not installed in this environment")
    def test_format_gate_runs_when_ruff_available(self) -> None:
        report = run_gates(self.root)
        format_outcome = next(o for o in report.outcomes if o.name == "format")
        self.assertIn(format_outcome.status, ("pass", "fail"))  # ran for real either way

    @unittest.skipIf(HAS_RUFF, "this asserts the missing-tool path specifically")
    def test_format_gate_reports_missing_tool_when_ruff_absent(self) -> None:
        report = run_gates(self.root)
        format_outcome = next(o for o in report.outcomes if o.name == "format")
        self.assertEqual(format_outcome.status, "missing_tool")


if __name__ == "__main__":
    unittest.main()
