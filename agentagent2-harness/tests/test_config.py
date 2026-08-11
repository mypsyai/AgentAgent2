"""Tests for agentagent2.config."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentagent2.config import Config, load_config


class TestConfigDefaults(unittest.TestCase):
    def test_defaults_are_sane(self) -> None:
        cfg = Config()
        self.assertEqual(cfg.model, "claude-sonnet-4-20250514")
        self.assertIsNone(cfg.api_key)
        self.assertFalse(cfg.mock)
        self.assertEqual(cfg.max_steps, 24)

    def test_require_api_key_raises_when_missing(self) -> None:
        cfg = Config(api_key=None)
        with self.assertRaises(ValueError):
            cfg.require_api_key()

    def test_require_api_key_raises_when_empty_string(self) -> None:
        cfg = Config(api_key="")
        with self.assertRaises(ValueError):
            cfg.require_api_key()

    def test_require_api_key_returns_key(self) -> None:
        cfg = Config(api_key="sk-test-123")
        self.assertEqual(cfg.require_api_key(), "sk-test-123")

    def test_config_is_frozen(self) -> None:
        cfg = Config()
        with self.assertRaises(AttributeError):
            cfg.model = "other-model"  # type: ignore[misc]


class TestLoadConfigPrecedence(unittest.TestCase):
    def test_env_overrides_defaults(self) -> None:
        cfg = load_config(env={"ANTHROPIC_API_KEY": "sk-env", "AGENTAGENT2_MODEL": "test-model"})
        self.assertEqual(cfg.api_key, "sk-env")
        self.assertEqual(cfg.model, "test-model")

    def test_explicit_overrides_beat_env(self) -> None:
        cfg = load_config(env={"AGENTAGENT2_MODEL": "env-model"}, model="explicit-model")
        self.assertEqual(cfg.model, "explicit-model")

    def test_none_overrides_do_not_clobber_env(self) -> None:
        # CLI flags that default to None (e.g. --model not passed) must not stomp on env/file.
        cfg = load_config(env={"AGENTAGENT2_MODEL": "env-model"}, model=None)
        self.assertEqual(cfg.model, "env-model")

    def test_config_file_is_lowest_precedence_above_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps({"model": "file-model", "max_steps": 5}))
            cfg = load_config(config_file=config_path, env={}, model="explicit-model")
            self.assertEqual(cfg.model, "explicit-model")  # explicit wins over file
            self.assertEqual(cfg.max_steps, 5)  # file wins over default

    def test_config_file_must_be_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps([1, 2, 3]))
            with self.assertRaises(ValueError):
                load_config(config_file=config_path, env={})

    def test_env_int_and_float_coercion(self) -> None:
        cfg = load_config(env={"AGENTAGENT2_MAX_STEPS": "7", "AGENTAGENT2_TEMPERATURE": "0.9"})
        self.assertEqual(cfg.max_steps, 7)
        self.assertAlmostEqual(cfg.temperature, 0.9)

    def test_env_invalid_int_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_config(env={"AGENTAGENT2_MAX_STEPS": "not-a-number"})

    def test_env_mock_bool_parsing(self) -> None:
        for truthy in ("1", "true", "True", "yes", "on"):
            self.assertTrue(load_config(env={"AGENTAGENT2_MOCK": truthy}).mock, truthy)
        for falsy in ("0", "false", "no", "off", ""):
            self.assertFalse(load_config(env={"AGENTAGENT2_MOCK": falsy}).mock, falsy)

    def test_workspace_override_is_coerced_to_path(self) -> None:
        cfg = load_config(env={}, workspace="/tmp/somewhere")
        self.assertIsInstance(cfg.workspace, Path)
        self.assertEqual(cfg.workspace, Path("/tmp/somewhere"))

    def test_unknown_override_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_config(env={}, not_a_real_field="x")


if __name__ == "__main__":
    unittest.main()
