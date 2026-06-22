"""Application configuration for the Aegis gateway.

Settings load from environment variables (prefix ``AEGIS_``) and an optional
``.env`` file via pydantic-settings.

F1 scope: this models ONLY the gateway/runtime fields plus optional provider
API keys. Later-phase variables that already appear in ``.env.example``
(``DATABASE_URL``, ``OTEL_*``, ``LANGFUSE_*``, ``AEGIS_JUDGE_MODEL``,
``AEGIS_EVAL_FAIL_UNDER``) are intentionally ignored here via ``extra="ignore"``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = {"critical", "error", "warning", "info", "debug"}


class Settings(BaseSettings):
    """Runtime configuration, sourced from env / ``.env``. No secrets hardcoded."""

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = Field(default="0.0.0.0", description="Bind address for the gateway.")
    port: int = Field(default=8080, ge=1, le=65535, description="Bind port.")

    # Upstream provider id. F1 ships ONLY "mock" (deterministic, keyless). The
    # planned real provider is Anthropic (Claude) as the primary option, with
    # OpenAI and Gemini as additional options — none are wired in F1.
    default_provider: str = Field(default="mock", description="Upstream provider id.")
    default_model: str = Field(default="mock/echo-1", description="Default model id.")
    log_level: str = Field(default="info", description="Logging level.")

    # Optional provider API keys. Read WITHOUT the AEGIS_ prefix to match the
    # conventional names in .env.example. Never required (F1 runs keyless on the
    # mock provider) and never logged or echoed in responses.
    anthropic_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    openai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    google_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY")
    )

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in _LOG_LEVELS else "info"


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance.

    Tests reset the cache with ``get_settings.cache_clear()`` to stay hermetic.
    """
    return Settings()
