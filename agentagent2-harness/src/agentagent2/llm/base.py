"""Core LLM types and the client protocol.

These types model the subset of the Anthropic Messages API the harness needs:
text blocks, tool-use blocks, and tool-result blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

JsonDict = dict[str, Any]


class LLMError(RuntimeError):
    """Raised when the model backend returns an error or malformed response."""


@dataclass(frozen=True)
class TextBlock:
    """A plain-text content block."""

    text: str

    def to_api(self) -> JsonDict:
        return {"type": "text", "text": self.text}


@dataclass(frozen=True)
class ToolUseBlock:
    """A request from the model to invoke a tool."""

    id: str
    name: str
    input: JsonDict

    def to_api(self) -> JsonDict:
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


@dataclass(frozen=True)
class ToolResultBlock:
    """The result of a tool invocation, sent back to the model."""

    tool_use_id: str
    content: str
    is_error: bool = False

    def to_api(self) -> JsonDict:
        return {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


@dataclass(frozen=True)
class Message:
    """A single conversation turn."""

    role: str
    content: list[ContentBlock]

    def to_api(self) -> JsonDict:
        return {"role": self.role, "content": [block.to_api() for block in self.content]}


@dataclass(frozen=True)
class LLMResponse:
    """A normalized model response."""

    stop_reason: str
    text: str
    tool_uses: list[ToolUseBlock]
    content_blocks: list[ContentBlock] = field(default_factory=list)
    raw: JsonDict = field(default_factory=dict)

    def assistant_message(self) -> Message:
        """Reconstruct the assistant turn to append to the running transcript."""
        blocks = self.content_blocks or ([TextBlock(self.text)] if self.text else [])
        return Message(role="assistant", content=list(blocks))


@runtime_checkable
class LLMClient(Protocol):
    """The minimal interface every model backend must implement."""

    def create(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[JsonDict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse: ...


def parse_content_blocks(content: list[JsonDict]) -> tuple[str, list[ToolUseBlock], list[ContentBlock]]:
    """Split an Anthropic ``content`` array into text, tool-uses, and ordered blocks."""
    text_parts: list[str] = []
    tool_uses: list[ToolUseBlock] = []
    blocks: list[ContentBlock] = []
    for item in content:
        kind = item.get("type")
        if kind == "text":
            text = str(item.get("text", ""))
            text_parts.append(text)
            blocks.append(TextBlock(text))
        elif kind == "tool_use":
            block = ToolUseBlock(
                id=str(item["id"]),
                name=str(item["name"]),
                input=dict(item.get("input", {})),
            )
            tool_uses.append(block)
            blocks.append(block)
    return "".join(text_parts), tool_uses, blocks
