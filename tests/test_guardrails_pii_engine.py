"""Tests for the PII engine selector (regex default; Presidio optional/lazy)."""

from __future__ import annotations

import importlib.util

import pytest

from aegis.gateway.config import Settings
from aegis.guardrails.pii_engine import select_pii_engine

_PRESIDIO_INSTALLED = importlib.util.find_spec("presidio_analyzer") is not None


def test_default_selects_regex_engine():
    engine = select_pii_engine(Settings(_env_file=None))  # gr_pii_engine defaults to "regex"
    text, entities = engine.redact("mail me at a@b.com")
    assert entities == ("EMAIL_ADDRESS",)
    assert "<EMAIL_ADDRESS>" in text


@pytest.mark.skipif(
    _PRESIDIO_INSTALLED, reason="exercises the missing-dependency path; presidio is installed"
)
def test_presidio_without_dependency_raises_clear_error():
    settings = Settings(_env_file=None, gr_pii_engine="presidio")
    with pytest.raises(RuntimeError, match=r"guardrails"):
        select_pii_engine(settings)


@pytest.mark.skipif(not _PRESIDIO_INSTALLED, reason="requires the optional [guardrails] extra")
def test_presidio_engine_redacts_email():
    settings = Settings(_env_file=None, gr_pii_engine="presidio")
    engine = select_pii_engine(settings)
    _, entities = engine.redact("mail me at a@b.com")
    assert "EMAIL_ADDRESS" in entities
