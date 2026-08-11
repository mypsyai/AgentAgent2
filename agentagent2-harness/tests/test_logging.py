"""Tests for agentagent2.logging."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from agentagent2.logging import AuditLog, utc_now


class TestUtcNow(unittest.TestCase):
    def test_format_is_iso8601_with_z_suffix(self) -> None:
        stamp = utc_now()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestAuditLog(unittest.TestCase):
    def test_writes_to_stream(self) -> None:
        stream = io.StringIO()
        log = AuditLog(stream=stream)
        log.event("test", "hello")
        output = stream.getvalue()
        self.assertIn("test: hello", output)
        self.assertTrue(output.endswith("\n"))

    def test_event_returns_the_formatted_line(self) -> None:
        stream = io.StringIO()
        log = AuditLog(stream=stream)
        line = log.event("kind", "message")
        self.assertIn("kind: message", line)
        self.assertRegex(line, r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\] kind: message$")

    def test_writes_to_file_when_path_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "audit.log"
            log = AuditLog(path, stream=io.StringIO())
            log.event("a", "first")
            log.event("b", "second")
            content = path.read_text()
            self.assertIn("a: first", content)
            self.assertIn("b: second", content)

    def test_file_is_append_only_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.log"
            AuditLog(path, stream=io.StringIO()).event("first", "one")
            AuditLog(path, stream=io.StringIO()).event("second", "two")
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("first: one", lines[0])
            self.assertIn("second: two", lines[1])

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "c" / "audit.log"
            AuditLog(path, stream=io.StringIO())
            self.assertTrue(path.parent.is_dir())

    def test_no_path_means_stream_only(self) -> None:
        stream = io.StringIO()
        log = AuditLog(stream=stream)
        log.event("x", "y")
        self.assertIn("x: y", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
