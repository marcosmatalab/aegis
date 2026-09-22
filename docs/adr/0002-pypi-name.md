# ADR 0002 — Publish as `aegis-control-plane`

**Status:** accepted · 2026-09-22

## Context

The repo had no release and nothing installable, so every path in required cloning first.
"Installable in one command" is one of the cheapest ways to change how a repository reads.

Measured with `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/<name>/json`:

| name | status |
|---|---|
| `aegis` | 200 — taken |
| `aegis-gateway` | 200 — taken |
| `aegis-llm` | 200 — taken |
| `aegis-control-plane` | **404 — free** |

## Decision

The **distribution** is `aegis-control-plane`. The repository, the import package and the
`aegis` console script are unchanged. "Control layer" is how the project already describes
itself in its own headline, so the name describes the thing rather than patching around a
conflict.

## Alternative rejected

**Don't publish; keep `pip install git+https://…`.** Saves a few hours. Rejected because a
`pipx install` on the first screen changes how the whole repo reads, and it is the only option
that also produces external signal, which was the weakest dimension of the project.

## Consequences

The package name and the repo name differ permanently — a small, cosmetic scar, resolved with
one line in the quickstart.

Two real bugs surfaced only because the package was actually built and installed: the sdist had
no include list and was sweeping up `node_modules`/`.next`/`.venv`, and the README's own
`pipx` + `--from-verdicts` instructions could not work, because a pipx user has no `artifacts/`
directory. Both are fixed; the artifact now ships inside the wheel.
