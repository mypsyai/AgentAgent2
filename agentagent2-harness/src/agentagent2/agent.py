"""The agentic tool-use loop: call the model, execute any requested tools, repeat.

This is the innermost cycle every higher-level workflow (the CLI, the server, the
nine-phase orchestrator in :mod:`agentagent2.phases`) is built on: create a model
response, and if it asked to use tools, run them and feed the results back, until the
model stops asking or ``max_steps`` is reached.
"""

from __future__ import annotations

from dataclasses import dataclass

from .llm.base import LLMClient, Message, TextBlock, ToolResultBlock
from .logging import AuditLog
from .tools.registry import ToolRegistry


@dataclass(frozen=True)
class StepRecord:
    """One model turn and the tool calls it triggered, kept for the transcript."""

    stop_reason: str
    text: str
    tool_calls: tuple[str, ...]


@dataclass(frozen=True)
class AgentResult:
    """The outcome of running the agent loop to completion or its step limit."""

    final_text: str
    stop_reason: str
    steps: tuple[StepRecord, ...]
    messages: list[Message]

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def hit_step_limit(self) -> bool:
        return self.stop_reason == "max_steps"


@dataclass
class AgentLoop:
    """Runs the create -> tool_use -> tool_result cycle until the model stops.

    Attributes:
        llm: The model backend.
        tools: The registry of callable tools (may be empty for a pure chat loop).
        system: The system prompt.
        max_tokens: Max tokens per model response.
        temperature: Sampling temperature.
        max_steps: Maximum number of model calls before forcing a stop.
        log: Optional audit log; when given, each model call and tool call is recorded.
    """

    llm: LLMClient
    tools: ToolRegistry
    system: str
    max_tokens: int = 4096
    temperature: float = 0.2
    max_steps: int = 24
    log: AuditLog | None = None

    def run(self, task: str, *, messages: list[Message] | None = None) -> AgentResult:
        """Run the loop for ``task`` and return the final result.

        Args:
            task: The instruction for this turn; always appended as a new user message. When
                ``messages`` is ``None`` this becomes the first turn of a fresh conversation.
            messages: An existing transcript to continue instead of starting fresh.

        Returns:
            The final :class:`AgentResult`, including the full step-by-step transcript.
        """
        transcript: list[Message] = list(messages) if messages else []
        transcript.append(Message(role="user", content=[TextBlock(task)]))

        tool_specs = self.tools.specs()
        steps: list[StepRecord] = []
        stop_reason = "max_steps"
        final_text = ""

        for step_index in range(1, self.max_steps + 1):
            response = self.llm.create(
                system=self.system,
                messages=transcript,
                tools=tool_specs,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            transcript.append(response.assistant_message())
            if response.text:
                final_text = response.text
            self._log(
                f"step {step_index}: stop_reason={response.stop_reason} "
                f"tool_calls={len(response.tool_uses)}"
            )

            if not response.tool_uses:
                stop_reason = response.stop_reason or "end_turn"
                steps.append(StepRecord(stop_reason=stop_reason, text=response.text, tool_calls=()))
                break

            result_blocks: list[ToolResultBlock] = []
            tool_names: list[str] = []
            for call in response.tool_uses:
                self._log(f"  tool_use: {call.name}({_short(call.input)})")
                result = self.tools.dispatch(call)
                result_blocks.append(result)
                tool_names.append(call.name)

            transcript.append(Message(role="user", content=list(result_blocks)))
            steps.append(
                StepRecord(
                    stop_reason=response.stop_reason, text=response.text, tool_calls=tuple(tool_names)
                )
            )
        else:
            stop_reason = "max_steps"

        return AgentResult(
            final_text=final_text, stop_reason=stop_reason, steps=tuple(steps), messages=transcript
        )

    def _log(self, message: str) -> None:
        if self.log is not None:
            self.log.event("agent", message)


def _short(data: object, limit: int = 120) -> str:
    text = str(data)
    return text if len(text) <= limit else text[:limit] + "…"
