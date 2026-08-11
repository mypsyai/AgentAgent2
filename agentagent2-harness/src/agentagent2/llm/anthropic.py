"""Anthropic Messages API client implemented with the Python standard library.

No third-party dependencies are required: HTTP is performed via ``urllib``. The
transport is injectable so the request/response handling can be unit-tested
offline without network access.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from .base import JsonDict, LLMError, LLMResponse, Message, parse_content_blocks


class Transport(Protocol):
    """A pluggable HTTP transport."""

    def __call__(
        self, *, url: str, body: bytes, headers: dict[str, str], timeout: float
    ) -> tuple[int, bytes]: ...


def urllib_transport(
    *, url: str, body: bytes, headers: dict[str, str], timeout: float
) -> tuple[int, bytes]:
    """Default transport: perform the POST with :mod:`urllib`."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status = int(response.status)
            return status, response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - exercised via fake transport
        return int(exc.code), exc.read()


class AnthropicClient:
    """Talks to the Anthropic Messages API.

    Args:
        model: Model id.
        api_key: API key.
        base_url: API base URL (no trailing slash required).
        api_version: Value for the ``anthropic-version`` header.
        timeout_s: Per-request timeout in seconds.
        transport: Injectable HTTP transport (defaults to :func:`urllib_transport`).
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        api_version: str,
        timeout_s: float,
        transport: Transport | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version
        self._timeout_s = timeout_s
        self._transport: Transport = transport if transport is not None else urllib_transport

    def create(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[JsonDict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        payload: JsonDict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [message.to_api() for message in messages],
        }
        if tools:
            payload["tools"] = tools

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
        }
        url = f"{self._base_url}/v1/messages"

        status, raw_bytes = self._transport(
            url=url, body=body, headers=headers, timeout=self._timeout_s
        )
        return self._parse(status, raw_bytes)

    @staticmethod
    def _parse(status: int, raw_bytes: bytes) -> LLMResponse:
        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMError(f"Non-JSON response from API (status {status}).") from exc

        if not isinstance(parsed, dict):
            raise LLMError(f"Unexpected response shape from API (status {status}).")

        if status >= 400:
            error = parsed.get("error", {})
            detail = error.get("message") if isinstance(error, dict) else str(error)
            raise LLMError(f"API error {status}: {detail or parsed}")

        content = parsed.get("content", [])
        if not isinstance(content, list):
            raise LLMError("API response missing a valid 'content' array.")

        text, tool_uses, blocks = parse_content_blocks([dict(item) for item in content])
        return LLMResponse(
            stop_reason=str(parsed.get("stop_reason", "")),
            text=text,
            tool_uses=tool_uses,
            content_blocks=blocks,
            raw=parsed,
        )
