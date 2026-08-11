"""Tests for agentagent2.tools.base: sandbox resolution and argument helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentagent2.tools.base import (
    ToolError,
    optional_int,
    optional_str,
    require_str,
    resolve_within,
)


class TestResolveWithin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_relative_path_resolves_inside_root(self) -> None:
        resolved = resolve_within(self.root, "sub/file.txt")
        self.assertEqual(resolved, (self.root / "sub" / "file.txt").resolve())

    def test_root_itself_is_allowed(self) -> None:
        resolved = resolve_within(self.root, ".")
        self.assertEqual(resolved, self.root.resolve())

    def test_dot_dot_escape_is_rejected(self) -> None:
        with self.assertRaises(ToolError):
            resolve_within(self.root, "../outside.txt")

    def test_deep_dot_dot_escape_is_rejected(self) -> None:
        with self.assertRaises(ToolError):
            resolve_within(self.root, "sub/../../outside.txt")

    def test_absolute_path_outside_root_is_rejected(self) -> None:
        with self.assertRaises(ToolError):
            resolve_within(self.root, "/etc/passwd")

    def test_absolute_path_inside_root_is_allowed(self) -> None:
        absolute = str(self.root / "inside.txt")
        resolved = resolve_within(self.root, absolute)
        self.assertEqual(resolved, (self.root / "inside.txt").resolve())

    def test_sneaky_prefix_sibling_is_rejected(self) -> None:
        # A sibling directory that merely starts with the same characters as root must not
        # be treated as "inside" root via naive string prefix checks.
        sibling = self.root.parent / (self.root.name + "-evil")
        with self.assertRaises(ToolError):
            resolve_within(self.root, str(sibling))


class TestArgumentHelpers(unittest.TestCase):
    def test_require_str_returns_value(self) -> None:
        self.assertEqual(require_str({"path": "a.py"}, "path"), "a.py")

    def test_require_str_missing_key_raises(self) -> None:
        with self.assertRaises(ToolError):
            require_str({}, "path")

    def test_require_str_wrong_type_raises(self) -> None:
        with self.assertRaises(ToolError):
            require_str({"path": 5}, "path")

    def test_optional_str_missing_returns_none(self) -> None:
        self.assertIsNone(optional_str({}, "path"))

    def test_optional_str_present_returns_value(self) -> None:
        self.assertEqual(optional_str({"path": "a"}, "path"), "a")

    def test_optional_str_wrong_type_raises(self) -> None:
        with self.assertRaises(ToolError):
            optional_str({"path": 5}, "path")

    def test_optional_int_missing_returns_none(self) -> None:
        self.assertIsNone(optional_int({}, "n"))

    def test_optional_int_present_returns_value(self) -> None:
        self.assertEqual(optional_int({"n": 5}, "n"), 5)

    def test_optional_int_rejects_bool(self) -> None:
        # bool is a subclass of int in Python; must not be silently accepted as an integer arg.
        with self.assertRaises(ToolError):
            optional_int({"n": True}, "n")

    def test_optional_int_wrong_type_raises(self) -> None:
        with self.assertRaises(ToolError):
            optional_int({"n": "5"}, "n")


if __name__ == "__main__":
    unittest.main()
