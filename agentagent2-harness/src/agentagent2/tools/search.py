"""Content and filename search tools, sandboxed to the workspace root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .base import JsonDict, Tool, ToolError, ToolResult, optional_str, require_str, resolve_within

MAX_MATCHES = 200
MAX_FILES_SCANNED = 5000

_IGNORED_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules", ".venv"}
)


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_DIR_NAMES for part in path.parts)


@dataclass(frozen=True)
class GrepSearchTool(Tool):
    """Search file contents by regular expression within the workspace."""

    workspace: Path

    name: ClassVar[str] = "grep_search"
    description: ClassVar[str] = "Search file contents by regular expression within the workspace."
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression to search for."},
            "glob": {"type": "string", "description": "Restrict which files are searched, e.g. '**/*.py'."},
            "case_sensitive": {"type": "boolean", "description": "Default true."},
        },
        "required": ["pattern"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("read",)
    safety: ClassVar[str] = "safe"

    def run(self, arguments: JsonDict) -> ToolResult:
        pattern_str = require_str(arguments, "pattern")
        glob = optional_str(arguments, "glob") or "**/*"
        case_sensitive = arguments.get("case_sensitive", True)
        if not isinstance(case_sensitive, bool):
            raise ToolError("Argument 'case_sensitive' must be a boolean when provided.")

        try:
            pattern = re.compile(pattern_str, 0 if case_sensitive else re.IGNORECASE)
        except re.error as exc:
            raise ToolError(f"Invalid regular expression: {exc}") from exc

        root = self.workspace.resolve()
        matches: list[str] = []
        scanned = 0
        for path in sorted(root.glob(glob)):
            if not path.is_file() or _is_ignored(path):
                continue
            scanned += 1
            if scanned > MAX_FILES_SCANNED:
                break
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(f"{path.relative_to(root)}:{lineno}: {line.strip()}")
                    if len(matches) >= MAX_MATCHES:
                        break
            if len(matches) >= MAX_MATCHES:
                break

        if not matches:
            return ToolResult(content="No matches.")
        suffix = f"\n...[truncated at {MAX_MATCHES} matches]" if len(matches) >= MAX_MATCHES else ""
        return ToolResult(content="\n".join(matches) + suffix)


@dataclass(frozen=True)
class GlobSearchTool(Tool):
    """Find files by name/path glob pattern within the workspace."""

    workspace: Path

    name: ClassVar[str] = "glob_search"
    description: ClassVar[str] = "Find files by name/path glob pattern within the workspace."
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'."},
            "path": {"type": "string", "description": "Subdirectory to search from (default: workspace root)."},
        },
        "required": ["pattern"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("read",)
    safety: ClassVar[str] = "safe"

    def run(self, arguments: JsonDict) -> ToolResult:
        pattern = require_str(arguments, "pattern")
        rel_path = optional_str(arguments, "path")
        base = resolve_within(self.workspace, rel_path) if rel_path else self.workspace.resolve()
        if not base.is_dir():
            raise ToolError(f"Not a directory: {rel_path!r}")

        root = self.workspace.resolve()
        results = sorted(str(p.relative_to(root)) for p in base.glob(pattern) if not _is_ignored(p))
        if not results:
            return ToolResult(content="No matches.")
        if len(results) > MAX_MATCHES:
            return ToolResult(content="\n".join(results[:MAX_MATCHES]) + f"\n...[truncated at {MAX_MATCHES}]")
        return ToolResult(content="\n".join(results))
