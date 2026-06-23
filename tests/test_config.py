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


# --- F2 guardrail settings -------------------------------------------------- #
def test_guardrails_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AEGIS_GUARDRAILS_ENABLED", raising=False)
    s = Settings(_env_file=None)
    assert s.guardrails_enabled is False
    # sub-flags default on, but are gated behind the master switch at runtime
    assert s.gr_injection_enabled is True
    assert s.gr_pii_redact_input is True
    assert s.gr_policy_enabled is True
    assert s.gr_output_pii_enabled is True
    assert s.gr_toxicity_enabled is True
    assert s.gr_output_pii_action == "block"
    assert s.gr_pii_engine == "regex"
    assert s.gr_toxicity_threshold == 0.5
    assert s.gr_policy_deny == []
    assert s.gr_policy_allow == []


def test_guardrails_master_toggle(monkeypatch):
    monkeypatch.setenv("AEGIS_GUARDRAILS_ENABLED", "true")
    s = Settings(_env_file=None)
    assert s.guardrails_enabled is True


def test_toxicity_threshold_out_of_range_rejected(monkeypatch):
    monkeypatch.setenv("AEGIS_GR_TOXICITY_THRESHOLD", "1.5")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_invalid_pii_engine_rejected(monkeypatch):
    monkeypatch.setenv("AEGIS_GR_PII_ENGINE", "magic")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_policy_rules_parsed_from_json_env(monkeypatch):
    monkeypatch.setenv("AEGIS_GR_POLICY_DENY", '["\\\\bsecret\\\\b", "forbidden"]')
    s = Settings(_env_file=None)
    assert s.gr_policy_deny == [r"\bsecret\b", "forbidden"]


# --- F3 judge settings ------------------------------------------------------ #
def test_judge_defaults(monkeypatch):
    for var in (
        "AEGIS_JUDGE_BACKEND",
        "AEGIS_JUDGE_MODEL",
        "AEGIS_JUDGE_TEMPERATURE",
        "AEGIS_JUDGE_MAX_TOKENS",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.judge_backend == "mock"
    assert s.judge_model == "anthropic/claude-opus-4-8"  # current Opus (was 4-6)
    assert s.judge_temperature == 0.0  # deterministic by default
    assert s.judge_max_tokens == 1024
    assert s.judge_ensemble_size == 3


def test_judge_model_read_from_aegis_prefixed_env(monkeypatch):
    monkeypatch.setenv("AEGIS_JUDGE_MODEL", "anthropic/claude-opus-4-8")
    assert Settings(_env_file=None).judge_model == "anthropic/claude-opus-4-8"


def test_judge_max_tokens_must_be_positive(monkeypatch):
    monkeypatch.setenv("AEGIS_JUDGE_MAX_TOKENS", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_judge_backend_override(monkeypatch):
    monkeypatch.setenv("AEGIS_JUDGE_BACKEND", "ensemble")
    assert Settings(_env_file=None).judge_backend == "ensemble"


def test_invalid_judge_backend_rejected(monkeypatch):
    monkeypatch.setenv("AEGIS_JUDGE_BACKEND", "oracle")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_judge_temperature_out_of_range_rejected(monkeypatch):
    monkeypatch.setenv("AEGIS_JUDGE_TEMPERATURE", "3.0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


# --- real Anthropic adapter settings ---------------------------------------- #
def test_anthropic_adapter_defaults(monkeypatch):
    for var in (
        "AEGIS_ANTHROPIC_MAX_TOKENS",
        "AEGIS_ANTHROPIC_BASE_URL",
        "AEGIS_ANTHROPIC_TIMEOUT_S",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.anthropic_max_tokens == 4096
    assert s.anthropic_base_url is None
    assert s.anthropic_timeout_s == 60.0


def test_anthropic_settings_override(monkeypatch):
    monkeypatch.setenv("AEGIS_ANTHROPIC_MAX_TOKENS", "256")
    monkeypatch.setenv("AEGIS_ANTHROPIC_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("AEGIS_ANTHROPIC_TIMEOUT_S", "5")
    s = Settings(_env_file=None)
    assert s.anthropic_max_tokens == 256
    assert s.anthropic_base_url == "http://localhost:9999"
    assert s.anthropic_timeout_s == 5.0


def test_anthropic_max_tokens_must_be_positive(monkeypatch):
    monkeypatch.setenv("AEGIS_ANTHROPIC_MAX_TOKENS", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_anthropic_timeout_must_be_positive(monkeypatch):
    monkeypatch.setenv("AEGIS_ANTHROPIC_TIMEOUT_S", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
