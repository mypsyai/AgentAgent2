"""Tool contracts, argument validation, and sandbox helpers.

Tools are the capabilities the agent may call. Every tool declares a JSON input
schema, a permission set, and a safety class, and runs inside a workspace
sandbox so file and shell operations cannot escape the project root.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

JsonDict = dict[str, Any]


class ToolError(Exception):
    """Raised for invalid arguments or disallowed operations.

    The registry converts these into structured error results for the model.
    """


@dataclass(frozen=True)
class ToolResult:
    """The outcome of a tool invocation."""

    content: str
    is_error: bool = False


class Tool(ABC):
    """Abstract base for all tools."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[JsonDict]
    permissions: ClassVar[tuple[str, ...]] = ()
    safety: ClassVar[str] = "safe"

    @abstractmethod
    def run(self, arguments: JsonDict) -> ToolResult:
        """Execute the tool with validated arguments."""

    def to_spec(self) -> JsonDict:
        """Return the Anthropic tool specification for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


# --- argument helpers -------------------------------------------------------


def require_str(arguments: JsonDict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise ToolError(f"Argument {key!r} must be a string.")
    return value


def optional_str(arguments: JsonDict, key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolError(f"Argument {key!r} must be a string when provided.")
    return value


def optional_int(arguments: JsonDict, key: str) -> int | None:
    value = arguments.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError(f"Argument {key!r} must be an integer when provided.")
    return value


# --- sandbox helper ---------------------------------------------------------


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` against ``root`` and forbid escaping the sandbox.

    Args:
        root: The workspace root.
        relative: A path supplied by the model (relative or absolute).

    Returns:
        The resolved absolute path, guaranteed to be inside ``root``.

    Raises:
        ToolError: If the resolved path would fall outside the sandbox.
    """
    root_resolved = root.resolve()
    candidate = Path(relative)
    combined = candidate if candidate.is_absolute() else root_resolved / candidate
    resolved = combined.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ToolError(f"Path escapes the workspace sandbox: {relative!r}")
    return resolved
