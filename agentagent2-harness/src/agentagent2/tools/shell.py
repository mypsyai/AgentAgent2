"""Shell execution tool: cwd confined to the workspace, with a bounded timeout."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .base import JsonDict, Tool, ToolError, ToolResult, optional_int, optional_str, require_str, resolve_within

DEFAULT_TIMEOUT_S = 30
MAX_TIMEOUT_S = 600
MAX_OUTPUT_CHARS = 20_000


@dataclass(frozen=True)
class RunShellTool(Tool):
    """Execute a shell command with its working directory confined to the workspace.

    Attributes:
        workspace: The sandbox root; ``cwd`` (if given) must resolve inside it.
        default_timeout_s: Timeout used when the model does not specify ``timeout_s``.
    """

    workspace: Path
    default_timeout_s: int = DEFAULT_TIMEOUT_S

    name: ClassVar[str] = "run_shell"
    description: ClassVar[str] = (
        "Execute a shell command in the sandbox (builds, git, project CLIs, test runners). Do "
        "not use this to read or edit files — use read_file/write_file/edit_file instead."
    )
    input_schema: ClassVar[JsonDict] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "cwd": {"type": "string", "description": "Working directory, relative to the workspace root."},
            "timeout_s": {"type": "integer", "description": f"Timeout in seconds (default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S})."},
        },
        "required": ["command"],
    }
    permissions: ClassVar[tuple[str, ...]] = ("exec",)
    safety: ClassVar[str] = "guarded"

    def run(self, arguments: JsonDict) -> ToolResult:
        command = require_str(arguments, "command")
        cwd_arg = optional_str(arguments, "cwd")
        cwd = resolve_within(self.workspace, cwd_arg) if cwd_arg else self.workspace.resolve()
        if not cwd.is_dir():
            raise ToolError(f"cwd is not a directory: {cwd_arg!r}")

        timeout = optional_int(arguments, "timeout_s")
        if timeout is None:
            timeout = self.default_timeout_s
        if timeout <= 0 or timeout > MAX_TIMEOUT_S:
            raise ToolError(f"timeout_s must be between 1 and {MAX_TIMEOUT_S}.")

        try:
            completed = subprocess.run(  # noqa: S602 - shell use is intentional; cwd is sandboxed
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"Command timed out after {timeout}s.") from exc
        except OSError as exc:
            raise ToolError(f"Failed to launch command: {exc}") from exc

        stdout = _truncate(completed.stdout)
        stderr = _truncate(completed.stderr)
        content = f"exit_code: {completed.returncode}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        return ToolResult(content=content, is_error=completed.returncode != 0)


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, {len(text) - limit} more characters]"
