"""FastAPI application entrypoint for the Aegis gateway.

For now this only exposes a ``/health`` liveness probe. The OpenAI-compatible
``/v1/chat/completions`` proxy, guardrails, and eval hooks land in later phases
(see the roadmap in the README).
"""

from __future__ import annotations

from fastapi import FastAPI

from aegis import __version__

app = FastAPI(
    title="Aegis Gateway",
    summary="Reliability + security + governance gateway for LLMs and agents.",
    version=__version__,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by orchestrators and the CI smoke test."""
    return {"status": "ok", "version": __version__}
