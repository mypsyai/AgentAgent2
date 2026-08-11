"""Sandboxed tool suite: filesystem, shell, and search tools, plus the registry."""

from __future__ import annotations

from pathlib import Path

from .base import JsonDict, Tool, ToolError, ToolResult, resolve_within
from .filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from .registry import ToolRegistry
from .search import GlobSearchTool, GrepSearchTool
from .shell import RunShellTool

__all__ = [
    "EditFileTool",
    "GlobSearchTool",
    "GrepSearchTool",
    "JsonDict",
    "ListDirTool",
    "ReadFileTool",
    "RunShellTool",
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "default_registry",
    "resolve_within",
    "WriteFileTool",
]


def default_registry(workspace: Path) -> ToolRegistry:
    """Build a :class:`ToolRegistry` with the standard sandboxed tool set bound to ``workspace``."""
    registry = ToolRegistry()
    registry.extend(
        [
            ReadFileTool(workspace=workspace),
            WriteFileTool(workspace=workspace),
            EditFileTool(workspace=workspace),
            ListDirTool(workspace=workspace),
            RunShellTool(workspace=workspace),
            GrepSearchTool(workspace=workspace),
            GlobSearchTool(workspace=workspace),
        ]
    )
    return registry
