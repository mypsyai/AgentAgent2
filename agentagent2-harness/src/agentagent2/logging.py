"""Append-only, timestamped logging for auditability.

Every significant event is appended with a UTC ISO-8601 timestamp. The log is
never truncated, matching AgentAgent2's auditability requirement.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditLog:
    """A minimal append-only logger.

    Writes to a file (when a path is given) and mirrors to a stream.
    """

    def __init__(self, path: str | Path | None = None, *, stream: TextIO | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._stream = stream if stream is not None else sys.stderr
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, message: str) -> str:
        """Append one event and return the formatted line."""
        line = f"[{utc_now()}] {kind}: {message}"
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        self._stream.write(line + "\n")
        self._stream.flush()
        return line
