"""Tests for agentagent2.tools.registry."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from agentagent2.llm.base import ToolUseBlock
from agentagent2.tools import default_registry
from agentagent2.tools.base import JsonDict, Tool, ToolError, ToolResult
from agentagent2.tools.registry import ToolRegistry


@dataclass(frozen=True)
class _EchoTool(Tool):
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "Echoes its input back."
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, arguments: JsonDict) -> ToolResult:
        return ToolResult(content=str(arguments.get("text", "")))


@dataclass(frozen=True)
class _AlwaysRaisesTool(Tool):
    name: ClassVar[str] = "boom"
    description: ClassVar[str] = "Always raises."
    input_schema: ClassVar[JsonDict] = {"type": "object", "properties": {}}

    def run(self, arguments: JsonDict) -> ToolResult:
        raise ToolError("deliberately broken")


@dataclass(frozen=True)
class _CrashesTool(Tool):
    name: ClassVar[str] = "crash"
    description: ClassVar[str] = "Raises something that is not a ToolError."
    input_schema: ClassVar[JsonDict] = {"type": "object", "properties": {}}

    def run(self, arguments: JsonDict) -> ToolResult:
        raise RuntimeError("unexpected")


class TestToolRegistry(unittest.TestCase):
    def test_register_and_specs(self) -> None:
        registry = ToolRegistry()
        registry.register(_EchoTool())
        specs = registry.specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["name"], "echo")
        self.assertIn("input_schema", specs[0])

    def test_registering_duplicate_name_raises(self) -> None:
        registry = ToolRegistry()
        registry.register(_EchoTool())
        with self.assertRaises(ValueError):
            registry.register(_EchoTool())

    def test_extend_returns_self_for_chaining(self) -> None:
        registry = ToolRegistry()
        returned = registry.extend([_EchoTool(), _AlwaysRaisesTool()])
        self.assertIs(returned, registry)
        self.assertEqual(registry.names(), ["boom", "echo"])

    def test_dispatch_success(self) -> None:
        registry = ToolRegistry().extend([_EchoTool()])
        call = ToolUseBlock(id="t1", name="echo", input={"text": "hi"})
        result = registry.dispatch(call)
        self.assertEqual(result.tool_use_id, "t1")
        self.assertEqual(result.content, "hi")
        self.assertFalse(result.is_error)

    def test_dispatch_unknown_tool(self) -> None:
        registry = ToolRegistry().extend([_EchoTool()])
        call = ToolUseBlock(id="t1", name="does_not_exist", input={})
        result = registry.dispatch(call)
        self.assertTrue(result.is_error)
        self.assertIn("Unknown tool", result.content)
        self.assertIn("echo", result.content)  # available tools are listed to help the model

    def test_dispatch_tool_error_becomes_error_result(self) -> None:
        registry = ToolRegistry().extend([_AlwaysRaisesTool()])
        call = ToolUseBlock(id="t1", name="boom", input={})
        result = registry.dispatch(call)
        self.assertTrue(result.is_error)
        self.assertIn("deliberately broken", result.content)

    def test_dispatch_unexpected_exception_does_not_propagate(self) -> None:
        registry = ToolRegistry().extend([_CrashesTool()])
        call = ToolUseBlock(id="t1", name="crash", input={})
        result = registry.dispatch(call)  # must not raise
        self.assertTrue(result.is_error)
        self.assertIn("unexpected", result.content)

    def test_names_are_sorted(self) -> None:
        registry = ToolRegistry().extend([_EchoTool(), _AlwaysRaisesTool(), _CrashesTool()])
        self.assertEqual(registry.names(), ["boom", "crash", "echo"])


class TestDefaultRegistry(unittest.TestCase):
    def test_default_registry_has_expected_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = default_registry(Path(tmp))
            self.assertEqual(
                registry.names(),
                sorted(
                    [
                        "read_file",
                        "write_file",
                        "edit_file",
                        "list_dir",
                        "run_shell",
                        "grep_search",
                        "glob_search",
                    ]
                ),
            )

    def test_default_registry_specs_are_valid_anthropic_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = default_registry(Path(tmp))
            for spec in registry.specs():
                self.assertIn("name", spec)
                self.assertIn("description", spec)
                self.assertIn("input_schema", spec)
                self.assertEqual(spec["input_schema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
