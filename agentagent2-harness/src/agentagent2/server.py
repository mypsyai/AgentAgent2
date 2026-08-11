"""A minimal HTTP API server, built entirely on the standard library's ``http.server``.

Endpoints:
    GET  /healthz  -> {"status": "ok", "version": ...}
    POST /v1/run   -> body {"task": str, "system": str?} -> agent result as JSON
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agent import AgentLoop
from .config import Config
from .llm import build_llm
from .tools import default_registry
from .version import __version__

MAX_BODY_BYTES = 1_000_000
DEFAULT_SYSTEM_PROMPT = (
    "You are AgentAgent2, a careful coding assistant. Use the available tools to complete the "
    "user's task. When you are done, reply with plain text and no further tool calls."
)


def make_handler(config: Config) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class bound to ``config``.

    ``http.server`` instantiates the handler once per request, so configuration is captured via
    this closure rather than passed through the constructor.
    """

    class Handler(BaseHTTPRequestHandler):
        server_version = f"AgentAgent2/{__version__}"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
            pass  # Quiet by default; wire to an AuditLog here if request logging is needed.

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok", "version": __version__})
                return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if self.path != "/v1/run":
                self._send_json(404, {"error": "not found"})
                return
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return

            task = payload.get("task")
            if not isinstance(task, str) or not task.strip():
                self._send_json(400, {"error": "'task' must be a non-empty string."})
                return
            system = payload.get("system", DEFAULT_SYSTEM_PROMPT)
            if not isinstance(system, str):
                self._send_json(400, {"error": "'system' must be a string when provided."})
                return

            try:
                loop = AgentLoop(
                    llm=build_llm(config),
                    tools=default_registry(config.workspace),
                    system=system,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    max_steps=config.max_steps,
                )
                result = loop.run(task)
            except Exception as exc:  # noqa: BLE001 - convert any failure into a JSON error response
                self._send_json(500, {"error": str(exc)})
                return

            self._send_json(
                200,
                {
                    "final_text": result.final_text,
                    "stop_reason": result.stop_reason,
                    "steps": result.step_count,
                },
            )

        def _read_json(self) -> dict[str, object]:
            length_header = self.headers.get("Content-Length", "0")
            try:
                length = int(length_header)
            except ValueError as exc:
                raise ValueError(f"Invalid Content-Length header: {length_header!r}") from exc
            if length <= 0:
                return {}
            if length > MAX_BODY_BYTES:
                raise ValueError(f"Request body too large (max {MAX_BODY_BYTES} bytes).")

            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSON body: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("JSON body must be an object.")
            return parsed

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(*, host: str, port: int, config: Config) -> None:
    """Start the HTTP API server and block until interrupted (Ctrl-C)."""
    handler = make_handler(config)
    with ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"AgentAgent2 serving on http://{host}:{port} (mock={config.mock})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
