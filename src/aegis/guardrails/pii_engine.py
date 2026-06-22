"""Selects the active PII engine from settings.

``regex`` (default) is the always-available deterministic engine; ``presidio``
is the optional Microsoft Presidio engine. Both expose ``redact(text)`` and
``scan(text)`` with identical output shape.
"""

from __future__ import annotations

from typing import Protocol

from aegis.gateway.config import Settings
from aegis.guardrails import pii


class PiiEngine(Protocol):
    def redact(self, text: str) -> tuple[str, tuple[str, ...]]: ...

    def scan(self, text: str) -> tuple[str, ...]: ...


def select_pii_engine(settings: Settings) -> PiiEngine:
    """Return the PII engine module for ``settings.gr_pii_engine``.

    Raises a clear ``RuntimeError`` if ``presidio`` is requested but its optional
    dependencies are not installed (the engine is never silently swapped).
    """
    if settings.gr_pii_engine == "presidio":
        from aegis.guardrails import pii_presidio

        pii_presidio.ensure_available()
        return pii_presidio
    return pii
