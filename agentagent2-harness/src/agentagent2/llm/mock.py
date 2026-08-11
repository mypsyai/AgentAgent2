"""An offline, deterministic mock LLM client for tests and dry runs.

Two modes:
- scripted: return a pre-built list of :class:`LLMResponse` objects in order.
- callback: delegate to a function of the running message list, enabling
  reactive mocks (e.g. respond based on the latest tool result).
"""

from __future__ import annotations

from collections.abc import Callable

from .base import JsonDict, LLMResponse, Message, TextBlock, ToolUseBlock

CreateFn = Callable[[list[Message]], LLMResponse]


def text_response(text: str, *, stop_reason: str = "end_turn") -> LLMResponse:
    """Build a final text response."""
    return LLMResponse(
        stop_reason=stop_reason,
        text=text,
        tool_uses=[],
        content_blocks=[TextBlock(text)] if text else [],
    )


def tool_call_response(
    name: str,
    tool_input: JsonDict,
    *,
    call_id: str = "call_1",
    text: str = "",
) -> LLMResponse:
    """Build a response that asks to invoke a single tool."""
    block = ToolUseBlock(id=call_id, name=name, input=tool_input)
    blocks: list[TextBlock | ToolUseBlock] = []
    if text:
        blocks.append(TextBlock(text))
    blocks.append(block)
    return LLMResponse(
        stop_reason="tool_use",
        text=text,
        tool_uses=[block],
        content_blocks=list(blocks),
    )


class MockLLMClient:
    """A deterministic stand-in for a real model backend."""

    def __init__(
        self,
        responses: list[LLMResponse] | None = None,
        *,
        on_create: CreateFn | None = None,
    ) -> None:
        if (responses is None) == (on_create is None):
            raise ValueError("Provide exactly one of 'responses' or 'on_create'.")
        self._responses = list(responses) if responses is not None else []
        self._on_create = on_create
        self._index = 0
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[JsonDict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self._on_create is not None:
            return self._on_create(messages)
        if self._index >= len(self._responses):
            raise AssertionError("MockLLMClient ran out of scripted responses.")
        response = self._responses[self._index]
        self._index += 1
        return response
