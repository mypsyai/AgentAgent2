"""Tests for agentagent2.cli."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentagent2 import cli
from agentagent2.version import __version__


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestVersionCommand(unittest.TestCase):
    def test_prints_version(self) -> None:
        code, out, _err = _run_cli(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), __version__)


class TestNoCommand(unittest.TestCase):
    def test_prints_help_and_returns_nonzero(self) -> None:
        code, out, _err = _run_cli([])
        self.assertEqual(code, 1)
        self.assertIn("usage", out.lower())


class TestRunCommand(unittest.TestCase):
    def test_mock_run_executes_tool_loop_and_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sample.txt").write_text("hi")
            code, out, _err = _run_cli(["run", "look around", "--workspace", tmp, "--mock"])
            self.assertEqual(code, 0)
            self.assertIn("Mock mode", out)

    def test_json_output_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _err = _run_cli(["run", "go", "--workspace", tmp, "--mock", "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertIn("final_text", payload)
            self.assertIn("stop_reason", payload)
            self.assertIn("steps", payload)

    def test_run_creates_workspace_if_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "nested" / "new"
            _run_cli(["run", "go", "--workspace", str(workspace), "--mock"])
            self.assertTrue(workspace.is_dir())

    def test_run_writes_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _run_cli(["run", "go", "--workspace", tmp, "--mock"])
            self.assertTrue((Path(tmp) / "agentagent2_run.log").exists())

    def test_run_without_mock_or_api_key_reports_error_not_traceback(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                code, _out, err = _run_cli(["run", "go", "--workspace", tmp])
                self.assertEqual(code, 1)
                self.assertIn("Error:", err)
            finally:
                if backup is not None:
                    os.environ["ANTHROPIC_API_KEY"] = backup


class TestGatesCommand(unittest.TestCase):
    def test_gates_command_reports_per_gate_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "pkg").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src" / "pkg" / "__init__.py").write_text("")
            (root / "tests" / "__init__.py").write_text("")
            (root / "tests" / "test_x.py").write_text(
                "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
            )
            code, out, _err = _run_cli(["gates", "--path", tmp])
            self.assertIn("tests", out)
            self.assertIn("coverage", out)
            self.assertIn(code, (0, 1))


class TestBuildParser(unittest.TestCase):
    def test_run_requires_task_argument(self) -> None:
        parser = cli._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["run"])

    def test_serve_defaults(self) -> None:
        parser = cli._build_parser()
        args = parser.parse_args(["serve"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8420)


if __name__ == "__main__":
    unittest.main()
