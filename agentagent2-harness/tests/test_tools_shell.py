"""Tests for agentagent2.tools.shell."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentagent2.tools.base import ToolError
from agentagent2.tools.shell import RunShellTool


class TestRunShellTool(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_runs_command_and_captures_stdout(self) -> None:
        result = RunShellTool(workspace=self.root).run({"command": "echo hello"})
        self.assertIn("hello", result.content)
        self.assertIn("exit_code: 0", result.content)
        self.assertFalse(result.is_error)

    def test_nonzero_exit_marks_is_error(self) -> None:
        result = RunShellTool(workspace=self.root).run({"command": "exit 3"})
        self.assertIn("exit_code: 3", result.content)
        self.assertTrue(result.is_error)

    def test_stderr_is_captured(self) -> None:
        result = RunShellTool(workspace=self.root).run({"command": "echo oops 1>&2"})
        self.assertIn("oops", result.content)

    def test_defaults_to_workspace_cwd(self) -> None:
        (self.root / "marker.txt").write_text("here")
        result = RunShellTool(workspace=self.root).run({"command": "ls"})
        self.assertIn("marker.txt", result.content)

    def test_explicit_cwd_relative_to_workspace(self) -> None:
        (self.root / "sub").mkdir()
        (self.root / "sub" / "inner.txt").write_text("x")
        result = RunShellTool(workspace=self.root).run({"command": "ls", "cwd": "sub"})
        self.assertIn("inner.txt", result.content)

    def test_cwd_escaping_sandbox_raises(self) -> None:
        with self.assertRaises(ToolError):
            RunShellTool(workspace=self.root).run({"command": "ls", "cwd": "../"})

    def test_cwd_must_be_a_directory(self) -> None:
        (self.root / "file.txt").write_text("x")
        with self.assertRaises(ToolError):
            RunShellTool(workspace=self.root).run({"command": "ls", "cwd": "file.txt"})

    def test_timeout_raises_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            RunShellTool(workspace=self.root, default_timeout_s=1).run({"command": "sleep 5"})

    def test_timeout_s_out_of_range_raises(self) -> None:
        with self.assertRaises(ToolError):
            RunShellTool(workspace=self.root).run({"command": "echo hi", "timeout_s": 0})
        with self.assertRaises(ToolError):
            RunShellTool(workspace=self.root).run({"command": "echo hi", "timeout_s": 99999})

    def test_output_is_truncated_when_huge(self) -> None:
        result = RunShellTool(workspace=self.root).run(
            {"command": "python3 -c \"print('x' * 30000)\""}
        )
        self.assertIn("truncated", result.content)
        self.assertLess(len(result.content), 30000)


if __name__ == "__main__":
    unittest.main()
