"""Tests for agentagent2.agent."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from agentagent2.agent import AgentLoop
from agentagent2.llm.base import Message, ToolResultBlock
from agentagent2.llm.mock import MockLLMClient, text_response, tool_call_response
from agentagent2.logging import AuditLog
from agentagent2.tools import default_registry
from agentagent2.tools.registry import ToolRegistry


class TestAgentLoopNoTools(unittest.TestCase):
    def test_single_end_turn_response(self) -> None:
        llm = MockLLMClient(responses=[text_response("all done")])
        loop = AgentLoop(llm=llm, tools=ToolRegistry(), system="sys")
        result = loop.run("do the thing")
        self.assertEqual(result.final_text, "all done")
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(result.step_count, 1)
        self.assertFalse(result.hit_step_limit)

    def test_first_user_message_carries_the_task(self) -> None:
        seen: list[Message] = []

        def on_create(messages: list[Message]) -> object:
            seen.extend(messages)
            return text_response("ok")

        llm = MockLLMClient(on_create=on_create)
        AgentLoop(llm=llm, tools=ToolRegistry(), system="sys").run("the actual task")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].role, "user")
        self.assertEqual(seen[0].content[0].text, "the actual task")  # type: ignore[union-attr]


class TestAgentLoopWithTools(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "hello.txt").write_text("hi")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_executes_a_tool_call_then_finishes(self) -> None:
        llm = MockLLMClient(
            responses=[
                tool_call_response("list_dir", {"path": "."}, call_id="c1"),
                text_response("I saw hello.txt"),
            ]
        )
        loop = AgentLoop(llm=llm, tools=default_registry(self.root), system="sys")
        result = loop.run("what's here?")
        self.assertEqual(result.final_text, "I saw hello.txt")
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.steps[0].tool_calls, ("list_dir",))
        self.assertEqual(result.steps[1].tool_calls, ())

    def test_tool_result_is_fed_back_to_the_model(self) -> None:
        captured: list[list[Message]] = []

        def on_create(messages: list[Message]) -> object:
            captured.append(list(messages))
            if len(captured) == 1:
                return tool_call_response("list_dir", {"path": "."}, call_id="c1")
            return text_response("done")

        llm = MockLLMClient(on_create=on_create)
        AgentLoop(llm=llm, tools=default_registry(self.root), system="sys").run("go")

        second_call_messages = captured[1]
        tool_result_blocks = [
            block for message in second_call_messages for block in message.content
            if isinstance(block, ToolResultBlock)
        ]
        self.assertEqual(len(tool_result_blocks), 1)
        self.assertIn("hello.txt", tool_result_blocks[0].content)

    def test_multiple_tool_calls_in_one_turn_all_get_results(self) -> None:
        from agentagent2.llm.base import LLMResponse, ToolUseBlock

        first_call = ToolUseBlock(id="c1", name="list_dir", input={"path": "."})
        second_call = ToolUseBlock(id="c2", name="read_file", input={"path": "hello.txt"})
        multi_tool_response = LLMResponse(
            stop_reason="tool_use",
            text="",
            tool_uses=[first_call, second_call],
            content_blocks=[first_call, second_call],
        )

        def on_create(messages: list[Message]) -> object:
            tool_result_count = sum(
                1 for m in messages for b in m.content if isinstance(b, ToolResultBlock)
            )
            return multi_tool_response if tool_result_count == 0 else text_response("done")

        llm = MockLLMClient(on_create=on_create)
        result = AgentLoop(llm=llm, tools=default_registry(self.root), system="sys").run("go")

        self.assertEqual(result.steps[0].tool_calls, ("list_dir", "read_file"))
        # [0]=user task, [1]=assistant (2 tool_uses), [2]=user (both tool_results together).
        tool_result_blocks = [b for b in result.messages[2].content if isinstance(b, ToolResultBlock)]
        self.assertEqual(len(tool_result_blocks), 2)
        self.assertEqual({b.tool_use_id for b in tool_result_blocks}, {"c1", "c2"})

    def test_unknown_tool_error_is_fed_back_not_raised(self) -> None:
        llm = MockLLMClient(
            responses=[
                tool_call_response("does_not_exist", {}, call_id="c1"),
                text_response("recovered"),
            ]
        )
        loop = AgentLoop(llm=llm, tools=default_registry(self.root), system="sys")
        result = loop.run("go")  # must not raise
        self.assertEqual(result.final_text, "recovered")


class TestAgentLoopStepLimit(unittest.TestCase):
    def test_hits_step_limit_when_model_never_stops(self) -> None:
        def on_create(_messages: list[Message]) -> object:
            return tool_call_response("list_dir", {"path": "."}, call_id="c1")

        with tempfile.TemporaryDirectory() as tmp:
            llm = MockLLMClient(on_create=on_create)
            loop = AgentLoop(
                llm=llm, tools=default_registry(Path(tmp)), system="sys", max_steps=3
            )
            result = loop.run("go forever")
            self.assertEqual(result.stop_reason, "max_steps")
            self.assertTrue(result.hit_step_limit)
            self.assertEqual(result.step_count, 3)


class TestAgentLoopContinuation(unittest.TestCase):
    def test_continuing_an_existing_transcript_appends_rather_than_restarts(self) -> None:
        prior = [Message(role="user", content=[])]
        seen_lengths: list[int] = []

        def on_create(messages: list[Message]) -> object:
            seen_lengths.append(len(messages))
            return text_response("ok")

        llm = MockLLMClient(on_create=on_create)
        AgentLoop(llm=llm, tools=ToolRegistry(), system="sys").run("next step", messages=prior)
        # prior (1) + newly appended user turn (1) = 2 messages sent to the model.
        self.assertEqual(seen_lengths, [2])


class TestAgentLoopLogging(unittest.TestCase):
    def test_logs_steps_when_log_is_given(self) -> None:
        stream = io.StringIO()
        log = AuditLog(stream=stream)
        llm = MockLLMClient(responses=[text_response("done")])
        AgentLoop(llm=llm, tools=ToolRegistry(), system="sys", log=log).run("go")
        self.assertIn("step 1", stream.getvalue())

    def test_no_log_means_no_error(self) -> None:
        llm = MockLLMClient(responses=[text_response("done")])
        # Must not raise even though log=None (the default).
        AgentLoop(llm=llm, tools=ToolRegistry(), system="sys").run("go")


if __name__ == "__main__":
    unittest.main()
