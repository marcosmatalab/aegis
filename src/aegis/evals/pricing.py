"""Static token price table for the CLEAR Cost dimension (F1.x).

``price_usd`` multiplies REAL usage tokens by a STATIC, manually-maintained list
price. The dollar figure is therefore an ESTIMATE, not a measurement — which is
exactly why CLEAR labels cost ``estimated`` (real measured tokens x assumed price),
distinct from the genuinely ``measured`` latency (real span wall-clock). See
``evals/clear.py``.

KEYING: the table is keyed on the PREFIXED gateway model id (e.g.
``anthropic/claude-opus-4-8``) — the exact form that flows through
``ChatCompletionResponse.model`` (``from_anthropic_message`` echoes the caller's
``request.model``). Any model with no entry returns ``None`` — including the
deterministic ``mock/echo-1`` (it has no entry, so a mock run can NEVER be assigned
a cost) and any unknown/typo'd model (``None`` is honest; a wrong-but-present price
would silently render as an estimate).

The prices below are public LIST prices (USD per 1K tokens) as of 2026-06; they are
manually maintained and may drift from negotiated/cached/tiered billing. Extend the
table to price more models — never guess a rate for one not listed.
"""

from __future__ import annotations

# model id (prefixed) -> (input_usd_per_1k, output_usd_per_1k)
_PRICE_USD_PER_1K: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus-4-8": (0.015, 0.075),
    "anthropic/claude-opus-4-7": (0.015, 0.075),
    "anthropic/claude-opus-4-6": (0.015, 0.075),
    "anthropic/claude-sonnet-4-6": (0.003, 0.015),
    "anthropic/claude-haiku-4-5": (0.0008, 0.004),
}

_USD_DECIMALS = 6  # cost rounding (matches the eval report's score precision)


def price_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """USD cost for ``prompt``+``completion`` tokens of ``model``, or ``None``.

    ``None`` whenever ``model`` is not in the table — the mock and any unknown model
    are unpriced by construction, so they can never produce an estimated cost.
    """
    rate = _PRICE_USD_PER_1K.get(model)
    if rate is None:
        return None
    in_rate, out_rate = rate
    cost = (prompt_tokens / 1000.0) * in_rate + (completion_tokens / 1000.0) * out_rate
    return round(cost, _USD_DECIMALS)


def is_priced(model: str) -> bool:
    """True if ``model`` has a price-table entry (False for the mock/unknown)."""
    return model in _PRICE_USD_PER_1K
