# Aegis dashboard (F9)

A **read-only** Next.js + Recharts dashboard that visualizes the **real reports** Aegis
already writes — `reports/eval-*.json`, `redteam-*.json`, `calibration.json`, and the
F8 `evidence-*.json`. It is part 1 of F9; the 2-minute demo GIF is part 2.

- **Real data only.** Every panel is derived from a report file read at request time. A
  missing report renders as an explicit "Not available" (with the command to produce
  it), never a zero, a blank, or a faked chart.
- **Statuses shown verbatim.** CLEAR (`measured`/`estimated`/`synthetic`/`placeholder`)
  and evidence (`covered`/`partial`/`not_covered`/`out_of_scope`) statuses are rendered
  as-is; only `measured`/`covered` get a success colour. Red-team named gaps, the κ
  caveats (small N, directional, undefined-when-degenerate), and the evidence
  partial-coverage note are surfaced, not buried. **The dashboard never paints a rosier
  picture than the reports.**
- **Offline.** No provider/model call, no network, no telemetry, system fonts only. It
  only ever **reads** the reports directory.

## Run it

```bash
cd dashboard
npm ci
npm run dev          # http://localhost:3000 — reads ../reports by default
```

Point it at a different reports directory:

```bash
AEGIS_REPORTS_DIR=/abs/path/to/reports npm run dev
```

Produce reports first (from the repo root), then refresh the page:

```bash
aegis eval run                  # -> reports/eval-<suite>.json
aegis redteam run               # -> reports/redteam-<suite>.json
aegis calibrate --judge geval   # -> reports/calibration.json   (needs ANTHROPIC_API_KEY)
aegis evidence --format json    # -> reports/evidence-<suite>.json
```

## Dev

`npm run lint` (Biome) · `npm run typecheck` (tsc) · `npm test` (Vitest) · `npm run build`

> `dashboard/fixtures/` holds **SAMPLE data for unit tests only — NOT real Aegis
> results**. The dashboard at runtime always reads the real `reports/` directory; it
> never reads the fixtures.
