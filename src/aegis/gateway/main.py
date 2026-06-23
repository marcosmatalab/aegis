"""FastAPI application entrypoint for the Aegis gateway.

Exposes a ``/health`` liveness probe and the OpenAI-compatible
``/v1/chat/completions`` proxy (F1). Guardrails and eval hooks land in later
phases (see the roadmap in the README).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aegis import __version__
from aegis.gateway.errors import register_exception_handlers
from aegis.gateway.proxy import router as proxy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own the real provider's lifecycle.

    Startup initialises the per-app provider cache + its build lock (so the lock is
    bound to the running loop, never a module global). The provider is deliberately
    NOT built here — construction stays lazy on the first request, so selecting
    ``anthropic`` with no key is a 500 RESPONSE, not a startup crash. Shutdown
    closes the cached provider's client (its httpx pool) exactly once.
    """
    app.state.provider = None
    app.state.provider_key = None
    app.state.provider_lock = asyncio.Lock()
    try:
        yield
    finally:
        provider = app.state.provider
        # Guard: the provider may never have been built (boot+shutdown with no
        # request, or only /health) — then there is nothing to close.
        if provider is not None:
            await provider.aclose()
        app.state.provider = None


app = FastAPI(
    title="Aegis Gateway",
    summary="Reliability + security + governance gateway for LLMs and agents.",
    version=__version__,
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(proxy_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by orchestrators and the CI smoke test."""
    return {"status": "ok", "version": __version__}
