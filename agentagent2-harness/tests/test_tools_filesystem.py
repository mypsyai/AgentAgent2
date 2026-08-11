"""Tests for agentagent2.tools.filesystem."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentagent2.tools.base import ToolError
from agentagent2.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool


class ToolTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestReadFileTool(ToolTestCase):
    def test_reads_full_file_with_line_numbers(self) -> None:
        (self.root / "a.txt").write_text("one\ntwo\nthree")
        result = ReadFileTool(workspace=self.root).run({"path": "a.txt"})
        self.assertIn(f"{1:>6}\tone", result.content)
        self.assertIn(f"{2:>6}\ttwo", result.content)
        self.assertIn(f"{3:>6}\tthree", result.content)
        self.assertFalse(result.is_error)

    def test_line_range_is_respected(self) -> None:
        (self.root / "a.txt").write_text("one\ntwo\nthree\nfour")
        result = ReadFileTool(workspace=self.root).run({"path": "a.txt", "start_line": 2, "end_line": 3})
        self.assertNotIn("one", result.content)
        self.assertIn("two", result.content)
        self.assertIn("three", result.content)
        self.assertNotIn("four", result.content)

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(ToolError):
            ReadFileTool(workspace=self.root).run({"path": "nope.txt"})

    def test_directory_raises(self) -> None:
        (self.root / "sub").mkdir()
        with self.assertRaises(ToolError):
            ReadFileTool(workspace=self.root).run({"path": "sub"})

    def test_binary_file_raises_tool_error(self) -> None:
        (self.root / "bin.dat").write_bytes(b"\xff\xfe\x00\x01binary")
        with self.assertRaises(ToolError):
            ReadFileTool(workspace=self.root).run({"path": "bin.dat"})

    def test_escaping_the_sandbox_raises(self) -> None:
        with self.assertRaises(ToolError):
            ReadFileTool(workspace=self.root).run({"path": "../outside.txt"})

    def test_empty_file(self) -> None:
        (self.root / "empty.txt").write_text("")
        result = ReadFileTool(workspace=self.root).run({"path": "empty.txt"})
        self.assertEqual(result.content, "(empty file)")

    def test_to_spec_shape(self) -> None:
        spec = ReadFileTool(workspace=self.root).to_spec()
        self.assertEqual(spec["name"], "read_file")
        self.assertIn("path", spec["input_schema"]["properties"])


class TestWriteFileTool(ToolTestCase):
    def test_creates_new_file(self) -> None:
        result = WriteFileTool(workspace=self.root).run({"path": "new.txt", "content": "hello"})
        self.assertEqual((self.root / "new.txt").read_text(), "hello")
        self.assertIn("Created", result.content)

    def test_overwrites_existing_file(self) -> None:
        (self.root / "existing.txt").write_text("old")
        result = WriteFileTool(workspace=self.root).run({"path": "existing.txt", "content": "new"})
        self.assertEqual((self.root / "existing.txt").read_text(), "new")
        self.assertIn("Overwrote", result.content)

    def test_creates_parent_directories(self) -> None:
        WriteFileTool(workspace=self.root).run({"path": "a/b/c.txt", "content": "deep"})
        self.assertEqual((self.root / "a" / "b" / "c.txt").read_text(), "deep")

    def test_non_string_content_raises(self) -> None:
        with self.assertRaises(ToolError):
            WriteFileTool(workspace=self.root).run({"path": "x.txt", "content": 5})

    def test_cannot_overwrite_a_directory(self) -> None:
        (self.root / "adir").mkdir()
        with self.assertRaises(ToolError):
            WriteFileTool(workspace=self.root).run({"path": "adir", "content": "x"})

    def test_escaping_the_sandbox_raises(self) -> None:
        with self.assertRaises(ToolError):
            WriteFileTool(workspace=self.root).run({"path": "../evil.txt", "content": "x"})


class TestEditFileTool(ToolTestCase):
    def test_replaces_unique_match(self) -> None:
        (self.root / "a.py").write_text("x = 1\ny = 2\n")
        result = EditFileTool(workspace=self.root).run(
            {"path": "a.py", "old_string": "x = 1", "new_string": "x = 100"}
        )
        self.assertEqual((self.root / "a.py").read_text(), "x = 100\ny = 2\n")
        self.assertIn("Edited", result.content)

    def test_no_match_raises(self) -> None:
        (self.root / "a.py").write_text("x = 1\n")
        with self.assertRaises(ToolError):
            EditFileTool(workspace=self.root).run(
                {"path": "a.py", "old_string": "not there", "new_string": "y"}
            )

    def test_non_unique_match_raises(self) -> None:
        (self.root / "a.py").write_text("x = 1\nx = 1\n")
        with self.assertRaises(ToolError):
            EditFileTool(workspace=self.root).run(
                {"path": "a.py", "old_string": "x = 1", "new_string": "x = 2"}
            )

    def test_identical_old_and_new_raises(self) -> None:
        (self.root / "a.py").write_text("x = 1\n")
        with self.assertRaises(ToolError):
            EditFileTool(workspace=self.root).run(
                {"path": "a.py", "old_string": "x = 1", "new_string": "x = 1"}
            )

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(ToolError):
            EditFileTool(workspace=self.root).run(
                {"path": "nope.py", "old_string": "a", "new_string": "b"}
            )

    def test_only_first_and_only_occurrence_replaced(self) -> None:
        (self.root / "a.py").write_text("UNIQUE_TOKEN\nother line\n")
        EditFileTool(workspace=self.root).run(
            {"path": "a.py", "old_string": "UNIQUE_TOKEN", "new_string": "REPLACED"}
        )
        content = (self.root / "a.py").read_text()
        self.assertEqual(content, "REPLACED\nother line\n")


class TestListDirTool(ToolTestCase):
    def test_lists_files_and_dirs(self) -> None:
        (self.root / "file.txt").write_text("x")
        (self.root / "subdir").mkdir()
        result = ListDirTool(workspace=self.root).run({})
        self.assertIn("f  file.txt", result.content)
        self.assertIn("d  subdir", result.content)

    def test_dirs_sort_before_files(self) -> None:
        (self.root / "zzz_file.txt").write_text("x")
        (self.root / "aaa_dir").mkdir()
        result = ListDirTool(workspace=self.root).run({})
        lines = result.content.splitlines()
        self.assertEqual(lines[0], "d  aaa_dir")
        self.assertEqual(lines[1], "f  zzz_file.txt")

    def test_empty_directory(self) -> None:
        result = ListDirTool(workspace=self.root).run({})
        self.assertEqual(result.content, "(empty directory)")

    def test_missing_directory_raises(self) -> None:
        with self.assertRaises(ToolError):
            ListDirTool(workspace=self.root).run({"path": "nope"})

    def test_file_path_raises(self) -> None:
        (self.root / "f.txt").write_text("x")
        with self.assertRaises(ToolError):
            ListDirTool(workspace=self.root).run({"path": "f.txt"})

    def test_subdirectory_listing(self) -> None:
        (self.root / "sub").mkdir()
        (self.root / "sub" / "inner.txt").write_text("x")
        result = ListDirTool(workspace=self.root).run({"path": "sub"})
        self.assertIn("inner.txt", result.content)


if __name__ == "__main__":
    unittest.main()
