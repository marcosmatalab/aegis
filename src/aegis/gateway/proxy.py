"""OpenAI-compatible ``POST /v1/chat/completions`` endpoint with the F2 guardrails.

Input guardrails run before dispatch, so a block is a clean JSON 400 in both the
streaming and non-streaming modes (nothing has been emitted yet). Output
guardrails run after the provider responds: on the non-stream path before the
JSONResponse; on the stream path the response is buffered, scanned, then emitted
(or replaced by a guardrail error frame). When output guardrails are inactive the
stream uses the original, non-buffering F1 generator, so behavior is identical.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from aegis.gateway.config import Settings, get_settings
from aegis.gateway.errors import GuardrailBlockedError
from aegis.gateway.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChunkChoice,
    Delta,
)
from aegis.gateway.upstream import Provider, build_provider
from aegis.guardrails import GuardrailPipeline, get_guardrail_pipeline
from aegis.guardrails.content import flatten_content

log = logging.getLogger("aegis.gateway")

router = APIRouter()

SSE_DONE = "data: [DONE]\n\n"
_STREAM_ERROR_MESSAGE = "The server had an error while streaming your request."


def get_provider(settings: Settings = Depends(get_settings)) -> Provider:
    """FastAPI dependency returning the active provider (overridable in tests)."""
    return build_provider(settings.default_provider)


def _error_frame(
    message: str, type_: str, *, code: str | None = None, param: str | None = None
) -> str:
    payload = {"error": {"message": message, "type": type_, "param": param, "code": code}}
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _serialize_chunk(chunk: ChatCompletionChunk) -> str:
    """Serialize a chunk as one SSE frame (compact JSON, like OpenAI).

    Drops unset top-level optionals (``usage``, ``system_fingerprint``) and the
    ``None`` fields of each ``delta`` (so the terminal delta is ``{}``), while
    keeping ``finish_reason`` (it lives inside ``choices``, never top-level None).
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
        # Headers/200 already sent; emit an OpenAI error frame and terminate
        # WITHOUT a [DONE] sentinel (OpenAI sends no [DONE] after an error).
        log.exception("Error during streaming: %s", exc)
        yield _error_frame(_STREAM_ERROR_MESSAGE, "api_error")
        return
    yield SSE_DONE


def _chunk_like(
    template: ChatCompletionChunk, *, delta: Delta, finish_reason: str | None
) -> ChatCompletionChunk:
    return ChatCompletionChunk(
        id=template.id,
        created=template.created,
        model=template.model,
        choices=[ChunkChoice(index=0, delta=delta, finish_reason=finish_reason)],
    )


async def _guarded_sse_generator(
    provider: Provider, request: ChatCompletionRequest, pipeline: GuardrailPipeline
) -> AsyncIterator[str]:
    """Buffer the whole stream, run output guardrails, then emit.

    Trades incremental delivery for leak-safe output scanning (the inherent
    guardrail/streaming tension). A block becomes a guardrail_blocked error frame
    with no [DONE]; a provider error stays an api_error frame.
    """
    chunks: list[ChatCompletionChunk] = []
    try:
        async for chunk in provider.stream(request):
            chunks.append(chunk)
    except Exception as exc:
        log.exception("Error during streaming: %s", exc)
        yield _error_frame(_STREAM_ERROR_MESSAGE, "api_error")
        return

    text = "".join(
        c.choices[0].delta.content for c in chunks if c.choices and c.choices[0].delta.content
    )
    result = await pipeline.check_output(text)
    if result.blocked:
        yield _error_frame(result.reason, "guardrail_blocked", code=result.code, param=result.param)
        return
    if result.redacted_text is not None and chunks:
        # Re-emit the redacted content as role -> content -> terminal frames,
        # carrying the provider's actual finish_reason from the last chunk (not a
        # hardcoded "stop"). NOTE (F2 limitation): a streamed usage object on the
        # final chunk is not reconstructed here; the mock never emits one.
        template = chunks[0]
        last_choices = chunks[-1].choices
        final_reason = last_choices[0].finish_reason if last_choices else "stop"
        yield _serialize_chunk(
            _chunk_like(template, delta=Delta(role="assistant"), finish_reason=None)
        )
        if result.redacted_text:
            yield _serialize_chunk(
                _chunk_like(template, delta=Delta(content=result.redacted_text), finish_reason=None)
            )
        yield _serialize_chunk(
            _chunk_like(template, delta=Delta(), finish_reason=final_reason or "stop")
        )
    else:
        for chunk in chunks:
            yield _serialize_chunk(chunk)
    yield SSE_DONE


def _first_choice_text(response: ChatCompletionResponse) -> str:
    if not response.choices:
        return ""
    return flatten_content(response.choices[0].message.content)


def _with_redacted_content(
    response: ChatCompletionResponse, redacted_text: str
) -> ChatCompletionResponse:
    choices = list(response.choices)
    first = choices[0]
    new_message = first.message.model_copy(update={"content": redacted_text})
    choices[0] = first.model_copy(update={"message": new_message})
    return response.model_copy(update={"choices": choices})


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    provider: Provider = Depends(get_provider),
    pipeline: GuardrailPipeline = Depends(get_guardrail_pipeline),
):
    # --- INPUT guardrails (before dispatch -> a block is a clean JSON 400) ---
    input_result = await pipeline.check_input(request)
    if input_result.blocked:
        raise GuardrailBlockedError(
            input_result.reason, code=input_result.code, param=input_result.param
        )
    if input_result.redacted_request is not None:
        request = input_result.redacted_request

    if request.stream:
        generator = (
            _guarded_sse_generator(provider, request, pipeline)
            if pipeline.output_active
            else _sse_generator(provider, request)
        )
        return StreamingResponse(
            generator, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    response = await provider.complete(request)
    # --- OUTPUT guardrails (non-stream) ---
    output_result = await pipeline.check_output(_first_choice_text(response))
    if output_result.blocked:
        raise GuardrailBlockedError(
            output_result.reason, code=output_result.code, param=output_result.param
        )
    if output_result.redacted_text is not None:
        response = _with_redacted_content(response, output_result.redacted_text)
    # exclude_none omits unset optionals (e.g. system_fingerprint), matching OpenAI.
    return JSONResponse(response.model_dump(exclude_none=True))
