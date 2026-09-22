# ADR 0003 — Ship the dashboard as a static export on GitHub Pages

**Status:** accepted · 2026-09-22

## Context

The dashboard was good work nobody could see: 41 Vitest tests passing, `tsc` clean, Biome
clean, a 24s build — and no way to look at it without cloning the repo and running `npm ci`.

It also carried **8 dependency advisories, one of them critical (`next`)**, all with fixes
available, in a repository whose subject is security.

The decisive property: the dashboard **only reads JSON files**. No backend, no database, no
state, no users, no authentication.

## Decision

Patch the advisories, then publish a **static export** over committed sample reports
(`dashboard/sample-reports/`, the real output of a real offline run) to GitHub Pages.

## Alternatives rejected

**Vercel with dynamic rendering.** Same effort, but ~€20/month with a domain and no
cold-start, and it buys nothing: there is nothing dynamic to serve. Everything the page does at
request time it can do at build time.

**Freeze it — keep the folder, don't deploy.** Saves two hours and costs nothing. Rejected
because it throws away 41 passing tests and a working build. That is not something to freeze;
it is something to show.

## Consequences

A "see it live" link on the first screen, at **€0**.

**The cost:** the published data is a snapshot, not a live run. Presenting a frozen view as
live would be exactly the quiet dishonesty this dashboard exists to avoid, so the page says so
itself and prints the command that reproduces it.

Two implementation notes worth recording. Next refuses to let `export const dynamic` be
branched on an environment variable, so the switch to build-time rendering is an explicit
`prepare-static-export.mjs` that **fails loudly if the page changes shape** — chosen over two
near-duplicate page files that would silently drift. And verifying the output caught the build
machine's absolute path leaking into the public HTML in two places (the header and each eval
run's file path); both are normalised at the source, and the workflow now greps the built HTML
and fails if a runner path appears.
