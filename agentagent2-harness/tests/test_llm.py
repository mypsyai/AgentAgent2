"""Tests for agentagent2.llm: base types, the Anthropic client, and the offline mock."""

from __future__ import annotations

import json
import unittest

from agentagent2.config import Config
from agentagent2.llm import build_llm
from agentagent2.llm.anthropic import AnthropicClient
from agentagent2.llm.base import (
    LLMError,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    parse_content_blocks,
)
from agentagent2.llm.mock import MockLLMClient, text_response, tool_call_response


class TestContentBlocks(unittest.TestCase):
    def test_text_block_to_api(self) -> None:
        self.assertEqual(TextBlock("hi").to_api(), {"type": "text", "text": "hi"})

    def test_tool_use_block_to_api(self) -> None:
        block = ToolUseBlock(id="t1", name="read_file", input={"path": "a.py"})
        self.assertEqual(
            block.to_api(), {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a.py"}}
        )

    def test_tool_result_block_to_api(self) -> None:
        block = ToolResultBlock(tool_use_id="t1", content="ok", is_error=False)
        self.assertEqual(
            block.to_api(), {"type": "tool_result", "tool_use_id": "t1", "content": "ok", "is_error": False}
        )

    def test_message_to_api_serializes_all_blocks(self) -> None:
        message = Message(role="user", content=[TextBlock("hi"), ToolResultBlock("t1", "ok")])
        api = message.to_api()
        self.assertEqual(api["role"], "user")
        self.assertEqual(len(api["content"]), 2)


class TestParseContentBlocks(unittest.TestCase):
    def test_extracts_text_only(self) -> None:
        text, tool_uses, blocks = parse_content_blocks([{"type": "text", "text": "hello"}])
        self.assertEqual(text, "hello")
        self.assertEqual(tool_uses, [])
        self.assertEqual(len(blocks), 1)

    def test_concatenates_multiple_text_blocks(self) -> None:
        text, _, _ = parse_content_blocks(
            [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        )
        self.assertEqual(text, "ab")

    def test_extracts_tool_use(self) -> None:
        text, tool_uses, blocks = parse_content_blocks(
            [{"type": "tool_use", "id": "t1", "name": "list_dir", "input": {"path": "."}}]
        )
        self.assertEqual(text, "")
        self.assertEqual(len(tool_uses), 1)
        self.assertEqual(tool_uses[0].name, "list_dir")
        self.assertEqual(len(blocks), 1)

    def test_mixed_text_and_tool_use_preserves_order(self) -> None:
        _, tool_uses, blocks = parse_content_blocks(
            [
                {"type": "text", "text": "thinking..."},
                {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "x"}},
            ]
        )
        self.assertEqual(len(tool_uses), 1)
        self.assertIsInstance(blocks[0], TextBlock)
        self.assertIsInstance(blocks[1], ToolUseBlock)

    def test_unknown_block_type_is_ignored(self) -> None:
        text, tool_uses, blocks = parse_content_blocks([{"type": "thinking", "text": "hmm"}])
        self.assertEqual(text, "")
        self.assertEqual(tool_uses, [])
        self.assertEqual(blocks, [])


class FakeTransport:
    """A scripted stand-in for agentagent2.llm.anthropic.Transport."""

    def __init__(self, status: int, body: dict[str, object]) -> None:
        self.status = status
        self.body = body
        self.calls: list[dict[str, object]] = []

    def __call__(self, *, url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        self.calls.append({"url": url, "body": json.loads(body), "headers": headers, "timeout": timeout})
        return self.status, json.dumps(self.body).encode("utf-8")


class TestAnthropicClient(unittest.TestCase):
    def _client(self, transport: FakeTransport) -> AnthropicClient:
        return AnthropicClient(
            model="claude-test",
            api_key="sk-test",
            base_url="https://api.example.com",
            api_version="2023-06-01",
            timeout_s=5.0,
            transport=transport,
        )

    def test_successful_text_response(self) -> None:
        transport = FakeTransport(
            200, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "hi there"}]}
        )
        client = self._client(transport)
        response = client.create(
            system="sys", messages=[], tools=[], max_tokens=100, temperature=0.0
        )
        self.assertEqual(response.text, "hi there")
        self.assertEqual(response.stop_reason, "end_turn")
        self.assertEqual(response.tool_uses, [])

    def test_tool_use_response_is_parsed(self) -> None:
        transport = FakeTransport(
            200,
            {
                "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "id": "t1", "name": "list_dir", "input": {"path": "."}}],
            },
        )
        response = self._client(transport).create(
            system="sys", messages=[], tools=[], max_tokens=100, temperature=0.0
        )
        self.assertEqual(response.stop_reason, "tool_use")
        self.assertEqual(len(response.tool_uses), 1)
        self.assertEqual(response.tool_uses[0].name, "list_dir")

    def test_request_payload_shape(self) -> None:
        transport = FakeTransport(200, {"stop_reason": "end_turn", "content": []})
        client = self._client(transport)
        messages = [Message(role="user", content=[TextBlock("hi")])]
        client.create(system="be nice", messages=messages, tools=[], max_tokens=50, temperature=0.3)

        call = transport.calls[0]
        self.assertEqual(call["url"], "https://api.example.com/v1/messages")
        self.assertEqual(call["headers"]["x-api-key"], "sk-test")
        self.assertEqual(call["headers"]["anthropic-version"], "2023-06-01")
        body = call["body"]
        self.assertEqual(body["model"], "claude-test")
        self.assertEqual(body["system"], "be nice")
        self.assertEqual(body["max_tokens"], 50)
        self.assertNotIn("tools", body)  # empty tool list is omitted, not sent as []

    def test_tools_included_when_nonempty(self) -> None:
        transport = FakeTransport(200, {"stop_reason": "end_turn", "content": []})
        client = self._client(transport)
        client.create(
            system="s", messages=[], tools=[{"name": "read_file"}], max_tokens=10, temperature=0.0
        )
        self.assertIn("tools", transport.calls[0]["body"])

    def test_http_error_status_raises_llm_error(self) -> None:
        transport = FakeTransport(429, {"error": {"message": "rate limited"}})
        with self.assertRaises(LLMError) as ctx:
            self._client(transport).create(
                system="s", messages=[], tools=[], max_tokens=10, temperature=0.0
            )
        self.assertIn("rate limited", str(ctx.exception))

    def test_billing_error_status_raises_llm_error(self) -> None:
        # Mirrors the real failure that killed the original AgentAgent2 harness session.
        transport = FakeTransport(400, {"error": {"type": "billing_error", "message": "credit balance too low"}})
        with self.assertRaises(LLMError) as ctx:
            self._client(transport).create(
                system="s", messages=[], tools=[], max_tokens=10, temperature=0.0
            )
        self.assertIn("credit balance too low", str(ctx.exception))

    def test_non_json_response_raises_llm_error(self) -> None:
        class BrokenTransport:
            def __call__(self, **_kwargs: object) -> tuple[int, bytes]:
                return 200, b"not json"

        with self.assertRaises(LLMError):
            self._client(BrokenTransport()).create(  # type: ignore[arg-type]
                system="s", messages=[], tools=[], max_tokens=10, temperature=0.0
            )

    def test_non_object_response_raises_llm_error(self) -> None:
        transport = FakeTransport(200, [])  # type: ignore[arg-type]
        with self.assertRaises(LLMError):
            self._client(transport).create(system="s", messages=[], tools=[], max_tokens=10, temperature=0.0)


class TestMockLLMClient(unittest.TestCase):
    def test_scripted_responses_are_returned_in_order(self) -> None:
        responses = [text_response("first"), text_response("second")]
        mock = MockLLMClient(responses=responses)
        first = mock.create(system="s", messages=[], tools=[], max_tokens=1, temperature=0.0)
        second = mock.create(system="s", messages=[], tools=[], max_tokens=1, temperature=0.0)
        self.assertEqual(first.text, "first")
        self.assertEqual(second.text, "second")

    def test_exhausting_scripted_responses_raises(self) -> None:
        mock = MockLLMClient(responses=[text_response("only")])
        mock.create(system="s", messages=[], tools=[], max_tokens=1, temperature=0.0)
        with self.assertRaises(AssertionError):
            mock.create(system="s", messages=[], tools=[], max_tokens=1, temperature=0.0)

    def test_on_create_callback_mode(self) -> None:
        mock = MockLLMClient(on_create=lambda messages: text_response(f"saw {len(messages)} messages"))
        response = mock.create(
            system="s", messages=[Message(role="user", content=[])], tools=[], max_tokens=1, temperature=0.0
        )
        self.assertEqual(response.text, "saw 1 messages")

    def test_requires_exactly_one_of_responses_or_on_create(self) -> None:
        with self.assertRaises(ValueError):
            MockLLMClient()
        with self.assertRaises(ValueError):
            MockLLMClient(responses=[text_response("x")], on_create=lambda m: text_response("y"))

    def test_records_calls(self) -> None:
        mock = MockLLMClient(responses=[text_response("x")])
        mock.create(system="sys-prompt", messages=[], tools=[], max_tokens=42, temperature=0.5)
        self.assertEqual(len(mock.calls), 1)
        self.assertEqual(mock.calls[0]["system"], "sys-prompt")
        self.assertEqual(mock.calls[0]["max_tokens"], 42)

    def test_tool_call_response_shape(self) -> None:
        response = tool_call_response("read_file", {"path": "a.py"}, call_id="c1", text="reading")
        self.assertEqual(response.stop_reason, "tool_use")
        self.assertEqual(len(response.tool_uses), 1)
        self.assertEqual(response.tool_uses[0].id, "c1")
        self.assertEqual(response.tool_uses[0].input, {"path": "a.py"})


class TestBuildLlm(unittest.TestCase):
    def test_mock_config_builds_mock_client(self) -> None:
        llm = build_llm(Config(mock=True))
        self.assertIsInstance(llm, MockLLMClient)

    def test_non_mock_config_builds_anthropic_client(self) -> None:
        llm = build_llm(Config(mock=False, api_key="sk-real"))
        self.assertIsInstance(llm, AnthropicClient)

    def test_non_mock_without_api_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_llm(Config(mock=False, api_key=None))

    def test_default_mock_llm_demonstrates_tool_loop(self) -> None:
        llm = build_llm(Config(mock=True))
        first = llm.create(system="s", messages=[], tools=[], max_tokens=10, temperature=0.0)
        self.assertEqual(first.stop_reason, "tool_use")
        self.assertEqual(first.tool_uses[0].name, "list_dir")

        transcript = [
            Message(role="user", content=[TextBlock("go")]),
            first.assistant_message(),
            Message(role="user", content=[ToolResultBlock(first.tool_uses[0].id, "f  a.py")]),
        ]
        second = llm.create(system="s", messages=transcript, tools=[], max_tokens=10, temperature=0.0)
        self.assertEqual(second.tool_uses, [])
        self.assertIn("Mock mode", second.text)


if __name__ == "__main__":
    unittest.main()
