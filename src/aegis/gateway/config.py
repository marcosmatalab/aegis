"""Application configuration for the Aegis gateway.

Settings load from environment variables (prefix ``AEGIS_``) and an optional
``.env`` file via pydantic-settings.

Scope: gateway/runtime fields, optional provider API keys, and the F2 guardrail
toggles/thresholds. Later-phase variables that already appear in ``.env.example``
(``DATABASE_URL``, ``OTEL_*``, ``LANGFUSE_*``, ``AEGIS_JUDGE_MODEL``,
``AEGIS_EVAL_FAIL_UNDER``) are intentionally ignored here via ``extra="ignore"``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

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

    # --- Real Anthropic provider adapter ------------------------------------
    # Used only when default_provider == "anthropic" (optional [anthropic] extra,
    # lazy-imported). Auth is anthropic_api_key above (env ANTHROPIC_API_KEY).
    anthropic_max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Default max_tokens for Anthropic (required upstream; optional in OpenAI).",
    )
    anthropic_base_url: str | None = Field(
        default=None, description="Override the Anthropic API base URL (proxies/testing)."
    )
    anthropic_timeout_s: float = Field(
        default=60.0, gt=0.0, description="Per-request timeout for Anthropic calls (seconds)."
    )

    # --- F2 guardrails -------------------------------------------------------
    # Master switch. Default FALSE so the gateway is a byte-identical passthrough
    # (F1 behavior) unless guardrails are explicitly turned on. Every sub-flag is
    # gated behind this: master off => the whole pipeline is a true no-op.
    guardrails_enabled: bool = Field(
        default=False, description="Master switch for the guardrails layer."
    )
    # Input guardrails (each gated behind the master switch).
    gr_injection_enabled: bool = Field(default=True, description="Prompt-injection check (LLM01).")
    gr_pii_redact_input: bool = Field(default=True, description="Redact PII before forwarding.")
    gr_policy_enabled: bool = Field(default=True, description="Allow/deny policy engine.")
    # Output guardrails.
    gr_output_pii_enabled: bool = Field(default=True, description="Detect PII leak in the output.")
    gr_output_pii_action: Literal["block", "redact"] = Field(
        default="block", description="What to do on output PII."
    )
    gr_toxicity_enabled: bool = Field(default=True, description="Basic output toxicity check.")
    gr_toxicity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Toxicity score threshold to block."
    )
    # PII engine. "regex" is the always-on deterministic default (no extra deps);
    # "presidio" uses Microsoft Presidio when the optional [guardrails] extra is
    # installed (lazy-imported).
    gr_pii_engine: Literal["regex", "presidio"] = Field(
        default="regex", description="PII detection engine."
    )
    # Policy rules (deny/allow), each a regex matched case-insensitively. Set via
    # JSON in the env (e.g. AEGIS_GR_POLICY_DENY='["\\bsecret\\b"]').
    gr_policy_deny: list[str] = Field(default_factory=list, description="Deny regex rules.")
    gr_policy_allow: list[str] = Field(default_factory=list, description="Allow-override regex.")

    # --- F3 evals / LLM-as-judge --------------------------------------------
    # Backend for the L2 judge. "mock" is deterministic and keyless (the default,
    # so the eval suite runs fully offline). "geval"/"ensemble" use a real LLM via
    # a provider — a clear stub in F3, never importing a paid SDK.
    judge_backend: Literal["mock", "geval", "ensemble"] = Field(
        default="mock", description="L2 judge backend."
    )
    judge_model: str = Field(
        default="anthropic/claude-opus-4-6", description="provider/model for the real judge."
    )
    judge_temperature: float = Field(
        default=0.0, ge=0.0, le=2.0, description="Judge sampling temperature (0 = deterministic)."
    )
    judge_ensemble_size: int = Field(
        default=3, ge=1, le=15, description="Number of judges in the ensemble backend."
    )

    # --- F4 Agent-as-a-Judge (trajectory) -----------------------------------
    # Backend for the trajectory judge. "mock" is a deterministic, keyless
    # pattern-based heuristic (the default, offline). "agent" uses a real LLM —
    # a clear stub in F4, never importing a paid SDK.
    agent_judge_backend: Literal["mock", "agent"] = Field(
        default="mock", description="Agent-as-a-Judge (trajectory) backend."
    )

    # Optional CLEAR budgets/SLOs. When set, the Cost/Latency dimensions get a
    # normalized 0..1 score (lower is better); otherwise only the raw value is
    # reported. None by default — Cost/Latency stay synthetic until F1.x.
    clear_cost_budget_usd: float | None = Field(
        default=None, ge=0.0, description="Per-case cost budget for CLEAR Cost normalization."
    )
    clear_latency_budget_ms: float | None = Field(
        default=None, ge=0.0, description="Per-case latency SLO for CLEAR Latency normalization."
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
