"""OpenAI-compatible error envelope and FastAPI exception handlers.

This is the single source of truth for the ``{"error": {...}}`` envelope. Every
error the gateway returns — request validation, known ``AegisError``s, and
unexpected exceptions — is rendered here so the wire shape is byte-identical.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.responses import JSONResponse

log = logging.getLogger("aegis.gateway")


# --------------------------------------------------------------------------- #
# Envelope model + builder
# --------------------------------------------------------------------------- #
class OpenAIErrorBody(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class OpenAIErrorEnvelope(BaseModel):
    error: OpenAIErrorBody


def error_response(
    *,
    status_code: int,
    message: str,
    type: str,
    param: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    """Build a JSONResponse with the exact OpenAI ``{"error": {...}}`` shape.

    ``param``/``code`` are always present (as ``null`` when unset), matching
    OpenAI, which includes the keys.
    """
    envelope = OpenAIErrorEnvelope(
        error=OpenAIErrorBody(message=message, type=type, param=param, code=code)
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


# --------------------------------------------------------------------------- #
# Exception hierarchy raised by gateway layers
# --------------------------------------------------------------------------- #
class AegisError(Exception):
    """Base for gateway errors that render as a clean OpenAI envelope."""

    status_code: int = 400
    type: str = "invalid_request_error"
    code: str | None = None
    param: str | None = None

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProviderNotConfiguredError(AegisError):
    """Raised when the selected provider has no F1 implementation.

    Treated as a server-side misconfiguration (5xx) rather than a client error:
    F1 only wires the deterministic ``mock`` provider. The planned real provider
    is Anthropic (Claude), with OpenAI and Gemini as additional options.
    """

    status_code = 500
    type = "api_error"
    code = "provider_not_configured"


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
def _param_from_loc(loc: tuple[Any, ...]) -> str | None:
    """Render a pydantic error ``loc`` as an OpenAI-style ``param`` path.

    Strips the leading ``"body"`` segment and renders dotted keys with ``[i]``
    list indices (e.g. ``messages[0].role``). Returns ``None`` for whole-body /
    unparseable-JSON failures (no field path).
    """
    parts = list(loc)
    if parts and parts[0] == "body":
        parts = parts[1:]
    if not parts or all(isinstance(p, int) for p in parts):
        return None
    out = ""
    for p in parts:
        if isinstance(p, int):
            out += f"[{p}]"
        else:
            out += ("." if out else "") + str(p)
    return out or None


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render request-body validation failures as HTTP 400 invalid_request_error.

    Overrides FastAPI's default 422 so OpenAI SDK clients (which branch on 400)
    keep working.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    if first.get("type") == "json_invalid":
        message: str = "We could not parse the JSON body of your request."
        param: str | None = None
    else:
        param = _param_from_loc(first.get("loc", ()))
        message = first.get("msg", "Invalid request.")
    return error_response(
        status_code=400, message=message, type="invalid_request_error", param=param
    )


async def aegis_exception_handler(request: Request, exc: AegisError) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        message=exc.message,
        type=exc.type,
        param=exc.param,
        code=exc.code,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback server-side only; clients get an opaque api_error.
    log.exception("Unhandled error in gateway: %s", exc)
    return error_response(
        status_code=500,
        message="The server had an error processing your request.",
        type="api_error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AegisError, aegis_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
