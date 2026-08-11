"""Runtime configuration for the AgentAgent2 harness.

Configuration precedence (lowest to highest):
1. Hard-coded defaults.
2. A JSON config file (if provided).
3. Environment variables.
4. Explicit keyword overrides.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_STEPS = 24
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_S = 120.0

DEFAULT_SYSTEM_PROMPT = (
    "You are an AI assistant with access to tools. Use them to complete the user's task. "
    "When you are done, reply with plain text and no further tool calls."
)


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration.

    Attributes:
        model: Anthropic model id.
        api_key: API key; ``None`` is allowed only in mock mode.
        api_token: Bearer token for authenticating HTTP API requests.
        base_url: API base URL.
        api_version: Anthropic API version header value.
        max_tokens: Max tokens per model response.
        max_steps: Max agent tool-use iterations before stopping.
        temperature: Sampling temperature.
        timeout_s: Per-request network timeout in seconds.
        workspace: Root directory the agent's tools are sandboxed to.
        mock: When true, use the offline mock LLM client.
        system_prompt_file: Path to a file containing the system prompt.
    """

    model: str = DEFAULT_MODEL
    api_key: str | None = None
    api_token: str | None = None
    base_url: str = DEFAULT_BASE_URL
    api_version: str = DEFAULT_API_VERSION
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_steps: int = DEFAULT_MAX_STEPS
    temperature: float = DEFAULT_TEMPERATURE
    timeout_s: float = DEFAULT_TIMEOUT_S
    workspace: Path = field(default_factory=Path.cwd)
    mock: bool = False
    system_prompt_file: Path | None = None

    def __post_init__(self) -> None:
        # Normalize blank/whitespace tokens to None so "no token" has one representation
        if self.api_token is not None and not self.api_token.strip():
            object.__setattr__(self, "api_token", None)
        if self.api_key is not None and not self.api_key.strip():
            object.__setattr__(self, "api_key", None)

    def require_api_key(self) -> str:
        """Return the API key or raise if it is missing in a non-mock context."""
        if self.api_key is None:
            raise ValueError(
                "No API key configured. Set ANTHROPIC_API_KEY or run with mock=True."
            )
        return self.api_key

    def load_system_prompt(self) -> str:
        """Load and return the system prompt from file, or return the default."""
        if self.system_prompt_file is None:
            return DEFAULT_SYSTEM_PROMPT
        path = self.system_prompt_file
        if not path.is_file():
            raise ValueError(f"System prompt file not found: {path}")
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"System prompt file is empty: {path}")
        return content


def _coerce_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Environment value for {field_name} must be an integer: {value!r}"
        ) from exc


def _coerce_float(value: str, field_name: str) -> float:
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Environment value for {field_name} must be a number: {value!r}"
        ) from exc


def load_config(
    *,
    config_file: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    **overrides: object,
) -> Config:
    """Build a :class:`Config` from file, environment, and explicit overrides.

    Args:
        config_file: Optional path to a JSON file with config keys.
        env: Environment mapping; defaults to ``os.environ``.
        **overrides: Explicit field overrides (highest precedence).

    Returns:
        A fully-resolved, immutable :class:`Config`.
    """
    environ = os.environ if env is None else env
    cfg = Config()

    if config_file is not None:
        raw = json.loads(Path(config_file).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Config file must contain a JSON object.")
        cfg = _apply_mapping(cfg, {str(k): v for k, v in raw.items()})

    cfg = _apply_env(cfg, environ)

    filtered = {k: v for k, v in overrides.items() if v is not None}
    if filtered:
        cfg = _apply_mapping(cfg, filtered)

    return cfg


def _apply_env(cfg: Config, environ: Mapping[str, str]) -> Config:
    if "ANTHROPIC_API_KEY" in environ:
        cfg = replace(cfg, api_key=environ["ANTHROPIC_API_KEY"])
    if "AGENTAGENT2_API_TOKEN" in environ:
        cfg = replace(cfg, api_token=environ["AGENTAGENT2_API_TOKEN"])
    if "AGENTAGENT2_MODEL" in environ:
        cfg = replace(cfg, model=environ["AGENTAGENT2_MODEL"])
    if "AGENTAGENT2_BASE_URL" in environ:
        cfg = replace(cfg, base_url=environ["AGENTAGENT2_BASE_URL"])
    if "AGENTAGENT2_MAX_TOKENS" in environ:
        cfg = replace(
            cfg, max_tokens=_coerce_int(environ["AGENTAGENT2_MAX_TOKENS"], "max_tokens")
        )
    if "AGENTAGENT2_MAX_STEPS" in environ:
        cfg = replace(
            cfg, max_steps=_coerce_int(environ["AGENTAGENT2_MAX_STEPS"], "max_steps")
        )
    if "AGENTAGENT2_TEMPERATURE" in environ:
        cfg = replace(
            cfg,
            temperature=_coerce_float(
                environ["AGENTAGENT2_TEMPERATURE"], "temperature"
            ),
        )
    if "AGENTAGENT2_WORKSPACE" in environ:
        cfg = replace(cfg, workspace=Path(environ["AGENTAGENT2_WORKSPACE"]))
    if "AGENTAGENT2_MOCK" in environ:
        cfg = replace(cfg, mock=_parse_bool(environ["AGENTAGENT2_MOCK"]))
    if "AGENTAGENT2_SYSTEM_PROMPT_FILE" in environ:
        cfg = replace(
            cfg, system_prompt_file=Path(environ["AGENTAGENT2_SYSTEM_PROMPT_FILE"])
        )
    return cfg


def _apply_mapping(cfg: Config, mapping: dict[str, object]) -> Config:
    changes: dict[str, object] = {}
    for key, value in mapping.items():
        if key == "workspace" and value is not None:
            changes[key] = Path(str(value))
        elif key == "system_prompt_file" and value is not None:
            changes[key] = Path(str(value))
        elif key in {"api_key", "api_token"}:
            changes[key] = None if value is None else str(value)
        elif key in {"model", "base_url", "api_version"}:
            changes[key] = str(value)
        elif key in {"max_tokens", "max_steps"}:
            changes[key] = _optional_int(value)
        elif key in {"temperature", "timeout_s"}:
            changes[key] = _optional_float(value)
        elif key == "mock":
            changes[key] = _parse_bool(value)
        else:
            raise ValueError(f"Unknown config key: {key!r}")
    return replace(cfg, **changes)


def _optional_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return int(str(value))


def _optional_float(value: object) -> float:
    if isinstance(value, float):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return float(str(value))


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
