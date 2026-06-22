"""Live Anthropic integration test — the ONLY test that hits the real API.

SKIPPED unless BOTH ``ANTHROPIC_API_KEY`` is set AND the optional ``[anthropic]``
SDK is installed. CI runs with neither, so this self-skips and the suite stays
green offline with no key. It costs a handful of tokens.

It exercises the STREAMING path on purpose: that is the richest translation
surface (message_start id+usage -> content_block_delta -> message_delta stop_reason
-> message_stop) and the one most likely to drift across SDK versions — it guards
that the real event shapes still match what the pure translators assume (notably
that finish_reason comes from message_delta and is never null).

Override the model with ``AEGIS_LIVE_TEST_MODEL`` (default: a current Claude Opus).
"""

from __future__ import annotations

import asyncio
import os

import pytest

from aegis.gateway.providers.anthropic_provider import AnthropicProvider, is_available
from aegis.gateway.schemas import ChatCompletionRequest

_KEY = os.getenv("ANTHROPIC_API_KEY")
_MODEL = os.getenv("AEGIS_LIVE_TEST_MODEL", "claude-opus-4-8")

pytestmark = pytest.mark.skipif(
    not _KEY or not is_available(),
    reason="requires ANTHROPIC_API_KEY and the optional [anthropic] extra",
)


def test_live_stream_maps_real_anthropic_events():
    provider = AnthropicProvider(api_key=_KEY, default_max_tokens=16)
    request = ChatCompletionRequest(
        model=_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly one word: pong"}],
        max_tokens=16,
        stream=True,
    )

    async def _run():
        return [chunk async for chunk in provider.stream(request)]

    chunks = asyncio.run(_run())

    # first chunk announces the assistant role
    assert chunks[0].choices[0].delta.role == "assistant"
    # at least one real content delta arrived
    assert any(c.choices[0].delta.content for c in chunks)
    # THE GUARD: terminal finish_reason is mapped from message_delta, never null
    assert chunks[-1].choices[0].finish_reason in {"stop", "length"}
    # a single, consistent id across the whole stream (adopted from message_start)
    assert len({c.id for c in chunks}) == 1
