# Aegis gateway — the OpenAI-compatible proxy, keyless by default.
#
# Two stages so the runtime image carries the built wheel and its dependencies,
# not the build toolchain or the source tree.
#
#   docker build -t aegis .
#   docker run --rm -p 8080:8080 aegis
#   curl localhost:8080/health
#
# The container runs the DETERMINISTIC MOCK PROVIDER by default: no API key, no
# network, no outbound call. To point it at real Claude, pass a key and switch
# the provider (see docs/provider-anthropic.md):
#
#   docker run --rm -p 8080:8080 \
#     -e AEGIS_DEFAULT_PROVIDER=anthropic -e ANTHROPIC_API_KEY=sk-ant-... aegis

# --- build ------------------------------------------------------------------ #
FROM python:3.12-slim AS build

WORKDIR /build
RUN pip install --no-cache-dir build

# Copy only what the wheel is built from, so an unrelated edit does not bust the layer.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY artifacts ./artifacts

RUN python -m build --wheel --outdir /dist

# --- runtime ---------------------------------------------------------------- #
FROM python:3.12-slim AS runtime

# uvicorn[standard] pulls uvloop/httptools wheels; no compiler needed at runtime.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AEGIS_HOST=0.0.0.0 \
    AEGIS_PORT=8080

# Never run the gateway as root: it is a network-facing process whose entire job
# is handling untrusted input.
RUN useradd --create-home --uid 10001 aegis
WORKDIR /home/aegis

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER aegis

EXPOSE 8080

# Exercises the real app, not just the process table.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "aegis.gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
