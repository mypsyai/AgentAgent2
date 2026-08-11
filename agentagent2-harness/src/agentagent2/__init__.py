"""AgentAgent2 harness: a deployable meta-agent runtime.

The package provides:
- an LLM client abstraction (`llm`) with an Anthropic implementation (stdlib urllib)
  and an offline mock,
- a sandboxed tool suite (`tools`),
- an agentic tool-use loop (`agent`),
- a nine-phase AgentAgent2 orchestrator (`phases`),
- quality gates (`gates`),
- a CLI (`cli`) and an HTTP API server (`server`).
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
