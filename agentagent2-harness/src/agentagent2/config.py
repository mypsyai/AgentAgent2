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
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_STEPS = 24
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration.

    Attributes:
        model: Anthropic model id.
        api_key: API key; ``None`` is allowed only in mock mode.
        base_url: API base URL.
        api_version: Anthropic API version header value.
        max_tokens: Max tokens per model response.
        max_steps: Max agent tool-use iterations before stopping.
        temperature: Sampling temperature.
        timeout_s: Per-request network timeout in seconds.
        workspace: Root directory the agent's tools are sandboxed to.
        mock: When true, use the offline mock LLM client.
    """

    model: str = DEFAULT_MODEL
    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    api_version: str = DEFAULT_API_VERSION
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_steps: int = DEFAULT_MAX_STEPS
    temperature: float = DEFAULT_TEMPERATURE
    timeout_s: float = DEFAULT_TIMEOUT_S
    workspace: Path = Path.cwd()
    mock: bool = False

    def require_api_key(self) -> str:
        """Return the API key or raise if it is missing in a non-mock context."""
        if self.api_key is None or self.api_key == "":
            raise ValueError(
                "No API key configured. Set ANTHROPIC_API_KEY or run with mock=True."
            )
        return self.api_key


def _coerce_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Environment value for {field} must be an integer: {value!r}") from exc


def _coerce_float(value: str, field: str) -> float:
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Environment value for {field} must be a number: {value!r}") from exc


def load_config(
    *,
    config_file: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
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


def _apply_env(cfg: Config, environ: dict[str, str]) -> Config:
    if "ANTHROPIC_API_KEY" in environ:
        cfg = replace(cfg, api_key=environ["ANTHROPIC_API_KEY"])
    if "AGENTAGENT2_MODEL" in environ:
        cfg = replace(cfg, model=environ["AGENTAGENT2_MODEL"])
    if "AGENTAGENT2_BASE_URL" in environ:
        cfg = replace(cfg, base_url=environ["AGENTAGENT2_BASE_URL"])
    if "AGENTAGENT2_MAX_TOKENS" in environ:
        cfg = replace(cfg, max_tokens=_coerce_int(environ["AGENTAGENT2_MAX_TOKENS"], "max_tokens"))
    if "AGENTAGENT2_MAX_STEPS" in environ:
        cfg = replace(cfg, max_steps=_coerce_int(environ["AGENTAGENT2_MAX_STEPS"], "max_steps"))
    if "AGENTAGENT2_TEMPERATURE" in environ:
        cfg = replace(
            cfg, temperature=_coerce_float(environ["AGENTAGENT2_TEMPERATURE"], "temperature")
        )
    if "AGENTAGENT2_WORKSPACE" in environ:
        cfg = replace(cfg, workspace=Path(environ["AGENTAGENT2_WORKSPACE"]))
    if "AGENTAGENT2_MOCK" in environ:
        cfg = replace(cfg, mock=_parse_bool(environ["AGENTAGENT2_MOCK"]))
    return cfg


def _apply_mapping(cfg: Config, mapping: dict[str, object]) -> Config:
    changes: dict[str, object] = {}
    for key, value in mapping.items():
        if key == "workspace" and value is not None:
            changes[key] = Path(str(value))
        elif key == "api_key":
            changes[key] = None if value is None else str(value)
        elif key in {"model", "base_url", "api_version"}:
            changes[key] = str(value)
        elif key in {"max_tokens", "max_steps"}:
            changes[key] = int(value)  # type: ignore[call-overload]
        elif key in {"temperature", "timeout_s"}:
            changes[key] = float(value)  # type: ignore[arg-type]
        elif key == "mock":
            changes[key] = _parse_bool(value)
        else:
            raise ValueError(f"Unknown config key: {key!r}")
    return replace(cfg, **changes)


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
