"""Tests for gateway configuration (pydantic-settings).

All tests pass ``_env_file=None`` so they never read the developer's real
``.env`` — the suite stays hermetic and deterministic.
"""

from __future__ import annotations

import pytest

from aegis.gateway.config import Settings, get_settings

_APP_VARS = (
    "AEGIS_HOST",
    "AEGIS_PORT",
    "AEGIS_DEFAULT_PROVIDER",
    "AEGIS_DEFAULT_MODEL",
    "AEGIS_LOG_LEVEL",
)
_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults(monkeypatch):
    for var in (*_APP_VARS, *_KEY_VARS):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.host == "0.0.0.0"
    assert s.port == 8080
    assert s.default_provider == "mock"
    assert s.log_level == "info"


def test_aegis_prefix_override(monkeypatch):
    monkeypatch.setenv("AEGIS_PORT", "9000")
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "anthropic")
    s = Settings(_env_file=None)
    assert s.port == 9000
    assert s.default_provider == "anthropic"


def test_provider_keys_read_unprefixed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "g-test")
    s = Settings(_env_file=None)
    assert s.anthropic_api_key == "sk-ant-test"
    assert s.openai_api_key == "sk-oai-test"
    assert s.google_api_key == "g-test"


def test_optional_keys_default_none(monkeypatch):
    for var in _KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.anthropic_api_key is None
    assert s.openai_api_key is None
    assert s.google_api_key is None


def test_port_out_of_range_rejected(monkeypatch):
    monkeypatch.setenv("AEGIS_PORT", "70000")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_invalid_log_level_falls_back(monkeypatch):
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "verbose")
    s = Settings(_env_file=None)
    assert s.log_level == "info"


def test_log_level_normalized_case(monkeypatch):
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "DEBUG")
    s = Settings(_env_file=None)
    assert s.log_level == "debug"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
