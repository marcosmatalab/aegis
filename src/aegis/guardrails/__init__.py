"""Aegis F2 guardrails — an input/output defense-in-depth layer for the gateway.

Cheap deterministic checks run first; a more expensive check runs only when
policy requires it. The whole layer is gated behind ``AEGIS_GUARDRAILS_ENABLED``
(default off), so with guardrails disabled the gateway behaves exactly like F1.
"""

from aegis.guardrails.pipeline import (
    GuardrailPipeline,
    build_pipeline,
    get_guardrail_pipeline,
)
from aegis.guardrails.result import GuardrailResult

__all__ = [
    "GuardrailPipeline",
    "GuardrailResult",
    "build_pipeline",
    "get_guardrail_pipeline",
]
