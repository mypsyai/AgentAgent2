"""Filesystem tools: read, write, edit, and list — all sandboxed to the workspace root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .base import (
    JsonDict,
    Tool,
    ToolError,
    ToolResult,
    optional_int,
    optional_str,
    require_str,
    resolve_within,
)


@dataclass(frozen=True)
class ReadFileTool(Tool):
    """Read a text file's contents, optionally restricted to a line range."""

    workspace: Path

    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = (
        "Read a text file, optionally a 1-indexed inclusive line range. Always inspect a file "
        "before editing it. Do not use this for images or binaries."
    )
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
            "start_line": {"type": "integer", "description": "1-indexed first line (optional)."},
            "end_line": {"type": "integer", "description": "1-indexed last line, inclusive (optional)."},
        },
        "required": ["path"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("read",)
    safety: ClassVar[str] = "safe"

    def run(self, arguments: JsonDict) -> ToolResult:
        rel = require_str(arguments, "path")
        path = resolve_within(self.workspace, rel)
        if not path.exists():
            raise ToolError(f"No such file: {rel!r}")
        if not path.is_file():
            raise ToolError(f"Not a file: {rel!r}")

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"File is not valid UTF-8 text: {rel!r}") from exc

        lines = text.splitlines()
        start = optional_int(arguments, "start_line")
        end = optional_int(arguments, "end_line")
        lo = max(1, start) if start is not None else 1
        hi = min(len(lines), end) if end is not None else len(lines)
        if not lines or lo > hi:
            return ToolResult(content="(empty file)" if not lines else "")

        numbered = "\n".join(f"{i:>6}\t{lines[i - 1]}" for i in range(lo, hi + 1))
        return ToolResult(content=numbered)


@dataclass(frozen=True)
class WriteFileTool(Tool):
    """Create a new file or fully replace an existing one."""

    workspace: Path

    name: ClassVar[str] = "write_file"
    description: ClassVar[str] = (
        "Create a new file or completely overwrite an existing one. For a targeted change to "
        "an existing file, prefer edit_file instead."
    )
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
            "content": {"type": "string", "description": "The full file content to write."},
        },
        "required": ["path", "content"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("write",)
    safety: ClassVar[str] = "guarded"

    def run(self, arguments: JsonDict) -> ToolResult:
        rel = require_str(arguments, "path")
        content = arguments.get("content")
        if not isinstance(content, str):
            raise ToolError("Argument 'content' must be a string.")

        path = resolve_within(self.workspace, rel)
        existed = path.exists()
        if existed and path.is_dir():
            raise ToolError(f"Cannot write_file over a directory: {rel!r}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        verb = "Overwrote" if existed else "Created"
        return ToolResult(content=f"{verb} {rel} ({len(content)} bytes).")


@dataclass(frozen=True)
class EditFileTool(Tool):
    """Replace an exact, unique string match within an existing file."""

    workspace: Path

    name: ClassVar[str] = "edit_file"
    description: ClassVar[str] = (
        "Replace an exact, unique string match within a file. Read the file first so the match "
        "is exact; include enough surrounding context that old_string is unique in the file."
    )
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
            "old_string": {"type": "string", "description": "Exact text to replace; must be unique."},
            "new_string": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old_string", "new_string"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("write",)
    safety: ClassVar[str] = "safe"

    def run(self, arguments: JsonDict) -> ToolResult:
        rel = require_str(arguments, "path")
        old = require_str(arguments, "old_string")
        new = arguments.get("new_string")
        if not isinstance(new, str):
            raise ToolError("Argument 'new_string' must be a string.")
        if old == new:
            raise ToolError("old_string and new_string are identical; nothing to do.")

        path = resolve_within(self.workspace, rel)
        if not path.is_file():
            raise ToolError(f"Not a file: {rel!r}")

        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            raise ToolError(f"old_string not found in {rel!r}.")
        if count > 1:
            raise ToolError(
                f"old_string is not unique in {rel!r} ({count} occurrences); include more context."
            )

        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolResult(content=f"Edited {rel} (1 replacement).")


@dataclass(frozen=True)
class ListDirTool(Tool):
    """List the immediate contents of a directory."""

    workspace: Path

    name: ClassVar[str] = "list_dir"
    description: ClassVar[str] = "List the immediate contents of a directory (non-recursive)."
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory, relative to the workspace root (default: root)."},
        },
    }
    permissions: ClassVar[tuple[str, ...]] = ("read",)
    safety: ClassVar[str] = "safe"

    def run(self, arguments: JsonDict) -> ToolResult:
        rel = optional_str(arguments, "path") or "."
        path = resolve_within(self.workspace, rel)
        if not path.exists():
            raise ToolError(f"No such directory: {rel!r}")
        if not path.is_dir():
            raise ToolError(f"Not a directory: {rel!r}")

        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not entries:
            return ToolResult(content="(empty directory)")
        lines = [f"{'d' if e.is_dir() else 'f'}  {e.name}" for e in entries]
        return ToolResult(content="\n".join(lines))
