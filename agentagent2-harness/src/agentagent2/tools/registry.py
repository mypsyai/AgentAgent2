"""Tool registry: aggregates tools, builds the Anthropic tool-spec list, and dispatches calls."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..llm.base import JsonDict, ToolResultBlock, ToolUseBlock
from .base import Tool, ToolError, ToolResult


@dataclass
class ToolRegistry:
    """Holds the active tool set and dispatches model tool-use requests to it."""

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Add one tool. Raises if a tool with the same name is already registered."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def extend(self, tools: list[Tool]) -> ToolRegistry:
        """Register several tools at once; returns self for chaining."""
        for tool in tools:
            self.register(tool)
        return self

    def specs(self) -> list[JsonDict]:
        """Return Anthropic tool specifications for every registered tool."""
        return [tool.to_spec() for tool in self._tools.values()]

    def names(self) -> list[str]:
        """Return the registered tool names, sorted."""
        return sorted(self._tools)

    def dispatch(self, call: ToolUseBlock) -> ToolResultBlock:
        """Execute one tool-use request and return the corresponding tool-result block.

        Unknown tools, invalid arguments (:class:`ToolError`), and unexpected exceptions are all
        converted into an error :class:`ToolResultBlock` rather than raised — a single bad tool
        call must never crash the agent loop.
        """
        tool = self._tools.get(call.name)
        if tool is None:
            available = ", ".join(self.names()) or "(none registered)"
            return ToolResultBlock(
                tool_use_id=call.id,
                content=f"Unknown tool: {call.name!r}. Available: {available}",
                is_error=True,
            )
        try:
            result: ToolResult = tool.run(call.input)
        except ToolError as exc:
            return ToolResultBlock(tool_use_id=call.id, content=str(exc), is_error=True)
        except Exception as exc:  # noqa: BLE001 - isolate tool failures from the agent loop
            return ToolResultBlock(
                tool_use_id=call.id, content=f"Unhandled tool error: {exc}", is_error=True
            )
        return ToolResultBlock(tool_use_id=call.id, content=result.content, is_error=result.is_error)
