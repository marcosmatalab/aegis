# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-09-22

First tagged release. F0–F9 complete, tested offline and keyless.

The **distribution** is published as `aegis-control-plane` because `aegis`, `aegis-gateway`
and `aegis-llm` are all taken on PyPI by other authors. The repository, the Python package and
the CLI command are all still `aegis`:

```bash
pipx install aegis-control-plane
aegis redteam run
```

### Added

**Gateway (F1, F1.x)**
- Drop-in OpenAI-compatible `POST /v1/chat/completions` (streaming and non-streaming) plus
  `/health`. Change a `base_url` and nothing else.
- Deterministic, keyless **mock provider** as the default, so every command in this repo runs
  with no API key and no network.
- Real **Anthropic / Claude** provider behind the same `Provider` ABC, lazily imported from the
  optional `[anthropic]` extra.
- Optional **OpenTelemetry** GenAI spans (~semconv v1.38), off by default; spans carry metadata
  only, never message content.

**Guardrails (F2)**
- Prompt-injection (OWASP LLM01), PII redaction (email, phone, Luhn-checked cards, Spanish
  DNI/NIE), allow/deny policy, and output toxicity. Off by default; a byte-identical
  passthrough when off. Optional Microsoft Presidio engine via `[guardrails]`.

**Evals and judge calibration (F3–F5)**
- L1/L2/L3 scoring, trajectory metrics and the CLEAR dimensions, each carrying an explicit
  honesty status (`measured` / `estimated` / `synthetic` / `placeholder`).
- `aegis calibrate` measures judge-vs-human agreement as Cohen's κ, reported with `p_o` and the
  full confusion matrix.
- **`--dump-verdicts` / `--from-verdicts`**: a real judge run can freeze its 30 per-case
  verdicts to a JSONL artifact, and anyone can recompute the published κ from that artifact
  **offline, with no API key and no network**. The artifact ships inside the wheel, so it works
  from a bare `pipx install` with no checkout.

**Red-team (F6) and CI gates (F7)**
- Committed OWASP-LLM-2025 attack catalog: **19/29 detected**, with the **10 that get through
  named in the report** rather than rounded away.
- `aegis eval gate` and `aegis redteam gate` compare a run to a committed baseline and exit
  non-zero on regression, naming every affected case or attack.

**Governance (F8) and dashboard (F9)**
- `aegis evidence` derives control statuses for EU AI Act Art.15 / NIST AI RMF / ISO 42001 from
  real artifacts — partial technical evidence, never a compliance certificate.
- Read-only Next.js dashboard over the real reports; a missing report renders as an explicit
  *Not available*, never a blank or faked chart.

**Packaging and CI**
- `Dockerfile` (`python:3.12-slim`, non-root, healthcheck) and a tag-triggered release workflow
  that attaches the wheel, the sdist and the real reports to the GitHub release.
- CI gates: `ruff`, `mypy`, `import-linter`, `pytest --cov-fail-under=95`, both regression
  gates, a κ-artifact recompute, and `npm audit --audit-level=high`. Python jobs install from
  the committed `uv.lock` on a 3.12 + 3.13 matrix.

### Changed
- `aegis.gateway.schemas` and `aegis.gateway.config` moved to **`aegis.core`**, removing a real
  `gateway ↔ guardrails` import cycle. `.importlinter` now pins the layering in CI.

### Fixed
- `mypy` cleaned from 22 errors to 0, including `dict` literals passed where `ChatMessage` was
  expected on the real judge's path, and a `str` widening in the evidence builder's status.
- Dashboard dependency advisories: 8 → 0 (one of them critical, in `next`).
- `scripts/demo.sh` no longer hardcodes the κ figure it promised not to hardcode; it recomputes
  it live from the committed artifact, and opens the browser only after the readiness wait.

[Unreleased]: https://github.com/marcosmatalab/aegis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/marcosmatalab/aegis/releases/tag/v0.1.0
