"""LLM client abstraction and implementations."""

from __future__ import annotations

from ..config import Config
from .anthropic import AnthropicClient, Transport, urllib_transport
from .base import (
    ContentBlock,
    JsonDict,
    LLMClient,
    LLMError,
    LLMResponse,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    parse_content_blocks,
)
from .mock import MockLLMClient, text_response, tool_call_response

__all__ = [
    "AnthropicClient",
    "ContentBlock",
    "JsonDict",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "Message",
    "MockLLMClient",
    "TextBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "Transport",
    "build_llm",
    "default_mock_llm",
    "parse_content_blocks",
    "text_response",
    "tool_call_response",
    "urllib_transport",
]


def build_llm(cfg: Config) -> LLMClient:
    """Build the configured model backend: the real Anthropic client, or the offline mock."""
    if cfg.mock:
        return default_mock_llm()
    return AnthropicClient(
        model=cfg.model,
        api_key=cfg.require_api_key(),
        base_url=cfg.base_url,
        api_version=cfg.api_version,
        timeout_s=cfg.timeout_s,
    )


def default_mock_llm() -> MockLLMClient:
    """A small, illustrative offline mock: lists the workspace once, then finishes.

    This exercises the real tool-use loop (one round trip through the tool registry) with no
    network access, so ``--mock`` / ``mock=True`` demonstrates actual mechanics rather than a
    single canned string.
    """

    def on_create(messages: list[Message]) -> LLMResponse:
        tool_results = sum(
            1 for message in messages for block in message.content if isinstance(block, ToolResultBlock)
        )
        if tool_results == 0:
            return tool_call_response(
                "list_dir", {"path": "."}, text="Mock mode: let's see what's already here."
            )
        return text_response(
            "Mock mode: no live model call was made. This canned response demonstrates the "
            "tool-use loop (one list_dir call above) without hitting the network."
        )

    return MockLLMClient(on_create=on_create)
