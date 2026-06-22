"""OpenAI-compatible ``POST /v1/chat/completions`` endpoint.

Branches on ``stream``:
  * non-streaming -> a single JSON ``chat.completion`` object;
  * streaming -> an SSE stream of ``chat.completion.chunk`` frames,
    ``data: {json}\\n\\n`` per chunk and a terminal ``data: [DONE]\\n\\n``.

The active provider is resolved via the ``get_provider`` FastAPI dependency, so
tests can swap it through ``app.dependency_overrides``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from aegis.gateway.config import Settings, get_settings
from aegis.gateway.schemas import ChatCompletionChunk, ChatCompletionRequest
from aegis.gateway.upstream import Provider, build_provider

log = logging.getLogger("aegis.gateway")

router = APIRouter()

SSE_DONE = "data: [DONE]\n\n"


def get_provider(settings: Settings = Depends(get_settings)) -> Provider:
    """FastAPI dependency returning the active provider (overridable in tests)."""
    return build_provider(settings.default_provider)


def _serialize_chunk(chunk: ChatCompletionChunk) -> str:
    """Serialize a chunk as one SSE frame (compact JSON, like OpenAI).

    Drops unset top-level optionals (``usage``, ``system_fingerprint``) so they
    are omitted rather than emitted as ``null`` — matching OpenAI's default
    stream. Also drops ``None`` fields from each ``delta`` so the terminal delta
    serializes as ``{}``. ``finish_reason`` is preserved (even as ``null``
    mid-stream) because it lives inside ``choices`` (never ``None`` at top level).
    """
    data = {k: v for k, v in chunk.model_dump().items() if v is not None}
    for choice in data["choices"]:
        choice["delta"] = {k: v for k, v in choice["delta"].items() if v is not None}
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n"


async def _sse_generator(provider: Provider, request: ChatCompletionRequest) -> AsyncIterator[str]:
    try:
        async for chunk in provider.stream(request):
            yield _serialize_chunk(chunk)
    except Exception as exc:
        # Headers/200 are already sent once streaming starts, so we cannot fall
        # back to a JSON error envelope; emit an OpenAI-style error frame and
        # terminate WITHOUT a [DONE] sentinel (OpenAI sends no [DONE] after an
        # error — [DONE] signals clean completion).
        log.exception("Error during streaming: %s", exc)
        err = {
            "error": {
                "message": "The server had an error while streaming your request.",
                "type": "api_error",
                "param": None,
                "code": None,
            }
        }
        yield f"data: {json.dumps(err, separators=(',', ':'))}\n\n"
        return
    yield SSE_DONE


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    provider: Provider = Depends(get_provider),
):
    if request.stream:
        return StreamingResponse(
            _sse_generator(provider, request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    response = await provider.complete(request)
    # exclude_none omits unset optionals (e.g. system_fingerprint), matching OpenAI.
    return JSONResponse(response.model_dump(exclude_none=True))
