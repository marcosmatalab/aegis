# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] — 2026-09-23

Red-team coverage grows and the headline rate falls with it. No change to the gateway, the
guardrails' behaviour or the scoring.

```bash
pipx install "git+https://github.com/marcosmatalab/aegis@v0.1.2"   # Python 3.12+
aegis redteam run   # overall: detected=19/29 rate=0.655, 10 known gaps
```

### Changed
- **The red-team detection rate falls, on purpose: 18/25 (0.720) → 19/29 (0.655), and the named
  gaps go 7 → 10.** Probing the guardrails directly turned up three evasions the catalog did not
  cover and the pipeline genuinely lets through: a French override (patterns cover English and
  Spanish only), a base64-wrapped override (the scanner decodes nothing), and zero-width-space
  splitting (no unicode normalisation). All three are catalogued as declared gaps. A fourth case,
  the same override via the `tool` role, is caught; it marks where the scanned-role boundary is.
  The red-team baseline, sample reports, dashboard screenshots, demo GIF, both READMEs,
  `docs/redteam.md`, `docs/limitations.md` and `SECURITY.md` carry the new figures.
- Red-team tests derive the catalog size from `load_attacks()` instead of hardcoding 25, so
  growing the catalog no longer breaks them for no reason.

### Added
- `docs/adr/`: decision records for the calibration artifact, distributing from git tags rather
  than PyPI, the static dashboard, the `aegis.core` layer, and letting the detection rate fall.

## [0.1.1] — 2026-09-23

Corrections to 0.1.0's documentation and release process. No change to the gateway, the
guardrails, the scoring or any published figure.

```bash
pipx install "git+https://github.com/marcosmatalab/aegis@v0.1.1"   # Python 3.12+
aegis redteam run
```

### Fixed
- **The LinkedIn badge pointed at someone else's profile.** It now links the author's profile
  under the author's name, and `tests/test_docs_links.py` fails on any other LinkedIn URL in
  the tracked tree.
- **This CHANGELOG described a release that did not exist.** 0.1.0 said "first tagged
  release" and gave a PyPI install command, but no tag existed and nothing is on PyPI.
  `v0.1.0` is now tagged on `954f5ff` (the merge of PR #40, the commit that carries
  version 0.1.0 and this file's `[0.1.0]` section) with its GitHub release, and every
  install line points at a tag. `tests/test_release_pipeline.py` fails on a PyPI install
  claim, on an install pinned to an unreleased version, and on a released version with no tag.
- `tests/test_docs_numbers.py` pinned only two of the four places the READMEs print the test
  count; the badge and the key-metrics cell could drift. All four are pinned now.
- **Nothing redeployed the live dashboard at release time.** `pages.yml` only ran on a
  `dashboard/**` change. It now also runs after every Release run and on demand.

### Removed
- The `pypi` job in `release.yml`. It had no trusted publisher and no token behind it, so it
  could only fail on every tag. The project is distributed from its tags; see
  [`docs/ci-gates.md`](docs/ci-gates.md#releasing).

## [0.1.0] — 2026-09-22

First tagged release. F0–F9 complete, tested offline and keyless.

The **distribution** is named `aegis-control-plane` because `aegis`, `aegis-gateway` and
`aegis-llm` are all taken on PyPI by other authors; it is not published to PyPI. The
repository, the Python package and the CLI command are all still `aegis`. Install this
release from its tag (Python 3.12+):

```bash
pipx install "git+https://github.com/marcosmatalab/aegis@v0.1.0"
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
- Committed OWASP-LLM-2025 attack catalog: **18/25 detected**, with the **7 that get through
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

[Unreleased]: https://github.com/marcosmatalab/aegis/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/marcosmatalab/aegis/releases/tag/v0.1.2
[0.1.1]: https://github.com/marcosmatalab/aegis/releases/tag/v0.1.1
[0.1.0]: https://github.com/marcosmatalab/aegis/releases/tag/v0.1.0
