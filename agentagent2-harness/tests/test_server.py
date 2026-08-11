"""Tests for agentagent2.server: real HTTP round trips against a background server thread."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from agentagent2.config import Config
from agentagent2.server import make_handler
from http.server import ThreadingHTTPServer


class ServerTestCase(unittest.TestCase):
    """Starts a real ThreadingHTTPServer on an OS-assigned port for each test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        workspace = Path(self._tmp.name)
        config = Config(mock=True, workspace=workspace)
        handler = make_handler(config)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def _request(self, method: str, path: str, body: object = None) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            payload = None if body is None else json.dumps(body).encode("utf-8")
            headers = {"Content-Type": "application/json"} if payload else {}
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return resp.status, parsed
        finally:
            conn.close()


class TestHealthz(ServerTestCase):
    def test_returns_ok_status(self) -> None:
        status, body = self._request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)

    def test_unknown_get_path_is_404(self) -> None:
        status, body = self._request("GET", "/nope")
        self.assertEqual(status, 404)
        self.assertIn("error", body)


class TestRunEndpoint(ServerTestCase):
    def test_runs_the_mock_agent_and_returns_result(self) -> None:
        status, body = self._request("POST", "/v1/run", {"task": "look around"})
        self.assertEqual(status, 200)
        self.assertIn("final_text", body)
        self.assertIn("stop_reason", body)
        self.assertIn("steps", body)
        self.assertIn("Mock mode", str(body["final_text"]))

    def test_missing_task_is_400(self) -> None:
        status, body = self._request("POST", "/v1/run", {})
        self.assertEqual(status, 400)
        self.assertIn("task", body["error"])

    def test_empty_task_is_400(self) -> None:
        status, _body = self._request("POST", "/v1/run", {"task": "   "})
        self.assertEqual(status, 400)

    def test_non_string_task_is_400(self) -> None:
        status, _body = self._request("POST", "/v1/run", {"task": 5})
        self.assertEqual(status, 400)

    def test_non_string_system_is_400(self) -> None:
        status, _body = self._request("POST", "/v1/run", {"task": "go", "system": 5})
        self.assertEqual(status, 400)

    def test_custom_system_prompt_is_accepted(self) -> None:
        status, body = self._request("POST", "/v1/run", {"task": "go", "system": "be terse"})
        self.assertEqual(status, 200)
        self.assertIn("final_text", body)

    def test_unknown_post_path_is_404(self) -> None:
        status, _body = self._request("POST", "/v1/other", {"task": "go"})
        self.assertEqual(status, 404)

    def test_malformed_json_body_is_400(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", "/v1/run", body=b"{not json", headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            resp.read()
        finally:
            conn.close()

    def test_empty_body_treated_as_missing_task(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", "/v1/run", body=b"", headers={})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            resp.read()
        finally:
            conn.close()


class TestMakeHandlerIsolation(unittest.TestCase):
    def test_two_handlers_from_different_configs_are_independent_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handler_a = make_handler(Config(mock=True, workspace=Path(tmp)))
            handler_b = make_handler(Config(mock=True, workspace=Path(tmp)))
            self.assertIsNot(handler_a, handler_b)


if __name__ == "__main__":
    unittest.main()
