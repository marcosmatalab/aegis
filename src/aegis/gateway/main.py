"""FastAPI application entrypoint for the Aegis gateway.

Exposes a ``/health`` liveness probe and the OpenAI-compatible
``/v1/chat/completions`` proxy (F1). Guardrails and eval hooks land in later
phases (see the roadmap in the README).
"""

from __future__ import annotations

from fastapi import FastAPI

from aegis import __version__
from aegis.gateway.errors import register_exception_handlers
from aegis.gateway.proxy import router as proxy_router

app = FastAPI(
    title="Aegis Gateway",
    summary="Reliability + security + governance gateway for LLMs and agents.",
    version=__version__,
)

register_exception_handlers(app)
app.include_router(proxy_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by orchestrators and the CI smoke test."""
    return {"status": "ok", "version": __version__}
