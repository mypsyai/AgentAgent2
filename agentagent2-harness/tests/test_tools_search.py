"""Tests for agentagent2.tools.search."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentagent2.tools.base import ToolError
from agentagent2.tools.search import GlobSearchTool, GrepSearchTool


class SearchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "a.py").write_text("def foo():\n    return 1\n")
        (self.root / "b.py").write_text("def bar():\n    return foo()\n")
        (self.root / "notes.txt").write_text("foo is mentioned here too\n")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "c.py").write_text("class Foo:\n    pass\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("foo\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestGrepSearchTool(SearchTestCase):
    def test_finds_matches_across_files(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "foo"})
        self.assertIn("a.py", result.content)
        self.assertIn("b.py", result.content)
        self.assertIn("notes.txt", result.content)

    def test_glob_restricts_search(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "foo", "glob": "**/*.py"})
        self.assertNotIn("notes.txt", result.content)
        self.assertIn("a.py", result.content)

    def test_git_directory_is_ignored(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "foo"})
        self.assertNotIn(".git", result.content)

    def test_case_insensitive_search(self) -> None:
        result = GrepSearchTool(workspace=self.root).run(
            {"pattern": "FOO", "glob": "**/*.py", "case_sensitive": False}
        )
        self.assertIn("a.py", result.content)

    def test_case_sensitive_by_default_misses(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "FOO", "glob": "**/*.py"})
        self.assertEqual(result.content, "No matches.")

    def test_no_matches(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "zzz_nonexistent"})
        self.assertEqual(result.content, "No matches.")

    def test_invalid_regex_raises(self) -> None:
        with self.assertRaises(ToolError):
            GrepSearchTool(workspace=self.root).run({"pattern": "("})

    def test_case_sensitive_wrong_type_raises(self) -> None:
        with self.assertRaises(ToolError):
            GrepSearchTool(workspace=self.root).run({"pattern": "foo", "case_sensitive": "yes"})

    def test_result_includes_line_number(self) -> None:
        result = GrepSearchTool(workspace=self.root).run({"pattern": "class Foo"})
        self.assertIn("c.py:1:", result.content)


class TestGlobSearchTool(SearchTestCase):
    def test_finds_matching_files(self) -> None:
        result = GlobSearchTool(workspace=self.root).run({"pattern": "**/*.py"})
        self.assertIn("a.py", result.content)
        self.assertIn("b.py", result.content)
        self.assertIn("sub/c.py", result.content.replace("\\", "/"))

    def test_restricts_to_extension(self) -> None:
        result = GlobSearchTool(workspace=self.root).run({"pattern": "*.txt"})
        self.assertIn("notes.txt", result.content)
        self.assertNotIn("a.py", result.content)

    def test_subdirectory_scoped_search(self) -> None:
        result = GlobSearchTool(workspace=self.root).run({"pattern": "*.py", "path": "sub"})
        self.assertIn("c.py", result.content)
        self.assertNotIn("a.py", result.content)

    def test_no_matches(self) -> None:
        result = GlobSearchTool(workspace=self.root).run({"pattern": "*.rs"})
        self.assertEqual(result.content, "No matches.")

    def test_git_directory_is_ignored(self) -> None:
        result = GlobSearchTool(workspace=self.root).run({"pattern": "**/*"})
        self.assertNotIn(".git", result.content)

    def test_nonexistent_subdirectory_raises(self) -> None:
        with self.assertRaises(ToolError):
            GlobSearchTool(workspace=self.root).run({"pattern": "*.py", "path": "nope"})


if __name__ == "__main__":
    unittest.main()
