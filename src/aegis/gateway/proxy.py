"""OpenAI-compatible ``POST /v1/chat/completions`` endpoint with the F2 guardrails.

Input guardrails run before dispatch, so a block is a clean JSON 400 in both the
streaming and non-streaming modes (nothing has been emitted yet). Output
guardrails run after the provider responds: on the non-stream path before the
JSONResponse; on the stream path the response is buffered, scanned, then emitted
(or replaced by a guardrail error frame). When output guardrails are inactive the
stream uses the original, non-buffering F1 generator, so behavior is identical.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from aegis.gateway import telemetry
from aegis.gateway.config import Settings, get_settings
from aegis.gateway.errors import AegisError, GuardrailBlockedError
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


async def get_provider(request: Request, settings: Settings = Depends(get_settings)) -> Provider:
    """Return the active provider, built ONCE per app and cached on ``app.state``.

    A real provider owns a network client (httpx pool); building it per request
    would never reuse connections and would leak clients. So it is built LAZILY on
    the first request, cached on ``app.state.provider``, and reused thereafter (the
    lifespan closes it on shutdown). Construction stays lazy (never at startup) so
    selecting ``anthropic`` with no key remains a 500 RESPONSE, not a startup crash.

    Still overridable in tests: ``app.dependency_overrides[get_provider]`` replaces
    this whole callable, so the cache is bypassed there.
    """
    state = request.app.state
    lock = getattr(state, "provider_lock", None)
    if lock is None:
        # The lifespan normally creates the lock at startup; a bare TestClient(app)
        # / ASGITransport runs no lifespan, so create it here on the running loop.
        # NOTE: no await between the None-check and the assignment, so this block is
        # atomic within the event loop — no other coroutine can interleave and
        # create a second lock before this one is stored.
        lock = asyncio.Lock()
        state.provider_lock = lock

    key = settings.default_provider
    cached = getattr(state, "provider", None)
    if cached is not None and getattr(state, "provider_key", None) == key:
        return cached

    async with lock:
        # Re-check after acquiring: another request may have built it meanwhile.
        cached = getattr(state, "provider", None)
        if cached is not None and getattr(state, "provider_key", None) == key:
            return cached
        if cached is not None:
            # The selected provider changed (e.g. mock -> anthropic). Clear the
            # cache BEFORE awaiting the close so no concurrent reader serves the
            # stale provider, then close it so its client/pool is not leaked.
            state.provider = None
            state.provider_key = None
            await cached.aclose()
        provider = build_provider(settings.default_provider, settings)  # may raise
        # Store ONLY on success: a failed build (e.g. anthropic + no key raises) is
        # never cached, so the next request re-raises and stays a clean 500.
        state.provider = provider
        state.provider_key = key
        return provider


def _error_frame(
    message: str, type_: str, *, code: str | None = None, param: str | None = None
) -> str:
    payload = {"error": {"message": message, "type": type_, "param": param, "code": code}}
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _exception_frame(exc: Exception) -> str:
    """SSE error frame for a mid-stream failure (headers/200 already committed).

    A mapped ``AegisError`` (e.g. an upstream rate_limit_error / unsupported
    feature) carries its real type/code so the client sees the precise reason;
    anything unexpected stays the opaque generic ``api_error`` (unchanged F1/F2
    behavior). No ``[DONE]`` follows an error, matching OpenAI."""
    if isinstance(exc, AegisError):
        return _error_frame(exc.message, exc.type, code=exc.code, param=exc.param)
    return _error_frame(_STREAM_ERROR_MESSAGE, "api_error")


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


def _stamp_stream_attrs(span: object, chunks: list[ChatCompletionChunk]) -> None:
    """Set GenAI response attrs on a streaming span from the observed chunks.

    Latency is the span's own duration; usage is set only if the provider emitted a
    terminal usage chunk (the mock never does, Anthropic only with include_usage) —
    otherwise the token attrs are honestly omitted, never fabricated."""
    if not chunks:
        return
    finish: str | None = None
    for chunk in chunks:
        if chunk.choices and chunk.choices[0].finish_reason:
            finish = chunk.choices[0].finish_reason
    usage = next((c.usage for c in chunks if getattr(c, "usage", None)), None)
    telemetry.set_response_attributes(
        span,
        model=chunks[0].model,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        finish_reason=finish,
    )


async def _sse_generator(
    provider: Provider, request: ChatCompletionRequest, span: object | None = None
) -> AsyncIterator[str]:
    # The span (when present) is started by the caller and ENDED HERE in finally, so
    # its duration spans real chunk emission and it closes on normal completion, on a
    # mid-stream error, AND on client-disconnect (GeneratorExit). The provider error
    # is swallowed-and-returned (no [DONE], matching OpenAI), so ERROR status is set
    # explicitly in the except block — a wrapping context manager would never see it.
    seen: list[ChatCompletionChunk] = []
    try:
        try:
            async for chunk in provider.stream(request):
                if span is not None:
                    seen.append(chunk)
                yield _serialize_chunk(chunk)
        except Exception as exc:
            # Headers/200 already sent; emit an OpenAI error frame and terminate
            # WITHOUT a [DONE] sentinel (OpenAI sends no [DONE] after an error).
            log.exception("Error during streaming: %s", exc)
            if span is not None:
                telemetry.mark_span_error(span, exc)
            yield _exception_frame(exc)
            return
        if span is not None:
            _stamp_stream_attrs(span, seen)
        yield SSE_DONE
    finally:
        if span is not None:
            span.end()


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
    provider: Provider,
    request: ChatCompletionRequest,
    pipeline: GuardrailPipeline,
    span: object | None = None,
) -> AsyncIterator[str]:
    """Buffer the whole stream, run output guardrails, then emit.

    Trades incremental delivery for leak-safe output scanning (the inherent
    guardrail/streaming tension). A block becomes a guardrail_blocked error frame
    with no [DONE]; a provider error stays an api_error frame. The span (when
    present) is ended HERE in finally and carries ERROR status on a provider error.
    """
    chunks: list[ChatCompletionChunk] = []
    try:
        try:
            async for chunk in provider.stream(request):
                chunks.append(chunk)
        except Exception as exc:
            log.exception("Error during streaming: %s", exc)
            if span is not None:
                telemetry.mark_span_error(span, exc)
            yield _exception_frame(exc)
            return

        if span is not None:
            _stamp_stream_attrs(span, chunks)
        text = "".join(
            c.choices[0].delta.content for c in chunks if c.choices and c.choices[0].delta.content
        )
        result = await pipeline.check_output(text)
        if result.blocked:
            yield _error_frame(
                result.reason, "guardrail_blocked", code=result.code, param=result.param
            )
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
                    _chunk_like(
                        template, delta=Delta(content=result.redacted_text), finish_reason=None
                    )
                )
            yield _serialize_chunk(
                _chunk_like(template, delta=Delta(), finish_reason=final_reason or "stop")
            )
        else:
            for chunk in chunks:
                yield _serialize_chunk(chunk)
        yield SSE_DONE
    finally:
        if span is not None:
            span.end()


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
    http_request: Request,
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

    # F1.x: the TracerProvider is installed on app.state ONLY when AEGIS_OTEL_ENABLED
    # (lifespan). When absent (the default), there is NO span, NO timing, NO added
    # work — a byte-identical F1/F2 passthrough. A no-op tracer is never even built.
    tracer_provider = getattr(http_request.app.state, "tracer_provider", None)

    if request.stream:
        span = None
        if tracer_provider is not None:
            span = telemetry.get_tracer(tracer_provider).start_span(
                telemetry.span_name(request.model)
            )
            telemetry.set_request_attributes(span, model=request.model, provider_name=provider.name)
        generator = (
            _guarded_sse_generator(provider, request, pipeline, span=span)
            if pipeline.output_active
            else _sse_generator(provider, request, span=span)
        )
        return StreamingResponse(
            generator, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    if tracer_provider is None:
        response = await provider.complete(request)
    else:
        # start_as_current_span auto-records the exception + sets ERROR on the way
        # out (the non-stream call re-raises, unlike the swallowing stream path), so
        # a provider failure is captured without manual handling here.
        tracer = telemetry.get_tracer(tracer_provider)
        with tracer.start_as_current_span(telemetry.span_name(request.model)) as span:
            telemetry.set_request_attributes(span, model=request.model, provider_name=provider.name)
            response = await provider.complete(request)
            telemetry.set_response_attributes(
                span,
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                finish_reason=response.choices[0].finish_reason if response.choices else None,
            )

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
