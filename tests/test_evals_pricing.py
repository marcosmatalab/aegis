"""Pure price-table tests — the structural 'mock can never be priced' invariant."""

from __future__ import annotations

import pytest

from aegis.evals.pricing import _PRICE_USD_PER_1K, is_priced, price_usd


def test_known_model_cost_is_tokens_times_rate():
    # 1000 in + 1000 out at (0.015, 0.075) per 1K = 0.015 + 0.075
    assert price_usd("anthropic/claude-opus-4-8", 1000, 1000) == pytest.approx(0.09)


def test_zero_tokens_is_zero_not_none_for_a_known_model():
    assert price_usd("anthropic/claude-opus-4-8", 0, 0) == 0.0


def test_mock_model_is_unpriced():
    # the mock has no table entry -> None -> it can NEVER yield an estimated cost
    assert price_usd("mock/echo-1", 10, 10) is None
    assert is_priced("mock/echo-1") is False


def test_unknown_model_is_none_not_a_wrong_estimate():
    assert price_usd("openai/gpt-4o", 100, 100) is None
    assert price_usd("totally-made-up", 100, 100) is None


def test_table_keyed_on_the_prefixed_gateway_model_id():
    # AnthropicProvider echoes response.model = request.model (PREFIXED, verified in
    # from_anthropic_message), so the bridge prices on the prefixed id a real
    # round-trip actually produces.
    assert is_priced("anthropic/claude-opus-4-8")
    assert price_usd("anthropic/claude-opus-4-8", 500, 250) is not None
    # the bare (un-prefixed) form must NOT accidentally match
    assert price_usd("claude-opus-4-8", 500, 250) is None


def test_every_row_is_well_formed():
    for model, rate in _PRICE_USD_PER_1K.items():
        assert model.count("/") == 1, f"{model!r} should be a prefixed id"
        assert isinstance(rate, tuple) and len(rate) == 2
        in_rate, out_rate = rate
        assert in_rate > 0 and out_rate > 0
