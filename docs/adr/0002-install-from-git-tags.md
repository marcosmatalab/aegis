# ADR 0002 — Distribute from git tags, not PyPI

**Status:** accepted · 2026-09-23 (release 0.1.1)

## Context

0.1.0 was described as installable from PyPI by its package name. On 2026-09-23 a clean clone
showed that none of the pieces behind that sentence existed:

| claim | measured |
|---|---|
| a `v0.1.0` tag | `git ls-remote --tags origin` → empty |
| the package on PyPI | `https://pypi.org/pypi/aegis-control-plane/json` → 404; `pip index versions aegis-control-plane` → "No matching distribution found" |
| a release page | the CHANGELOG's `releases/tag/v0.1.0` link → no such release |
| a working publish job | `release.yml` had a `pypi` job with no trusted publisher and no token, so it could only fail — and did, on the first tag |

Registering a PyPI trusted publisher needs the maintainer's PyPI account, which was not
available.

## Decision

A release is a `vX.Y.Z` git tag plus a GitHub release. The install line pins the tag:

```bash
pipx install "git+https://github.com/marcosmatalab/aegis@vX.Y.Z"   # Python 3.12+
```

`release.yml` re-runs the gates on the tagged code, builds the wheel and sdist, regenerates the
evidence reports offline and attaches all of it to the release. It has no PyPI job.

This is enforced, not just written down: `tests/test_release_pipeline.py` fails on a PyPI
install claim in any doc, on an install pinned to a version the CHANGELOG never released, on a
CHANGELOG release that is not the package version, and on any workflow step that publishes to
PyPI.

## Rejected alternative

**Keep the `pypi` job and the PyPI install line, and publish "later".** It reads better — a
one-word install by package name on the front page — but until a publisher exists it is a
claim nothing can satisfy, and a job that fails red on every tag. A version on PyPI is also
permanent and un-deletable, so it is the last place to experiment.

## Cost accepted

- Installing needs git and builds from source (a few seconds). There is no install by bare
  package name and no version pin against an index.
- Moving to PyPI later is a deliberate change, not a flag: register the trusted publisher, add
  the publish job, and change `test_no_workflow_publishes_to_pypi` and
  `test_no_document_promises_a_pypi_install` in the same PR.
- The distribution name stays `aegis-control-plane` in `pyproject.toml` (`aegis`,
  `aegis-gateway` and `aegis-llm` are taken on PyPI by other authors) even though nothing is
  published under it, so the name is ready if PyPI is ever adopted.

Operational detail: [`docs/ci-gates.md › Releasing`](../ci-gates.md#releasing).
