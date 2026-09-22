# Dashboard (F9)

![Eval scorecard and CLEAR dimensions, with every status shown verbatim](dashboard-eval.png)

![OWASP red-team panel: 19/29 detected and all 10 named gaps listed](dashboard-redteam.png)

![Judge calibration: Cohen's kappa 0.933 against human labels, with the confusion matrix](dashboard-kappa.png)

<sub>Real screenshots of a real run — the reports come straight from `bash scripts/demo.sh`.
Note the κ panel reads `judge=geval`: the dashboard shows the **real** measurement, recomputed
from the committed verdicts, not the mock's smoke-test number.</sub>


A **read-only** Next.js + Recharts dashboard (in [`dashboard/`](../dashboard/)) that visualizes the **real reports** Aegis already writes — `eval-*.json`, `redteam-*.json`, `calibration.json`, and the F8 `evidence-*.json`. It is part 1 of F9; the end-to-end [demo](../README.md#demo) is part 2 — both shipped.

> **Same crux as F8 — never rosier than the reports.** Every panel is derived from a report file read at request time (server-side, read-only); a missing report renders as an explicit **"Not available"** with the command to produce it, never a zero/blank/faked chart. Statuses are shown **verbatim** — CLEAR (`measured`/`estimated`/`synthetic`/`placeholder`) and evidence (`covered`/`partial`/`not_covered`/`out_of_scope`) — and only `measured`/`covered` get a success colour (enforced by a tested `statusTone`). Red-team **named gaps**, the κ caveats (small N, directional, undefined-when-degenerate), and the evidence partial-coverage note are surfaced, not buried. A trend line is drawn only for **≥2** real eval runs (else an honest absent note; no interpolation).

- **Offline.** No provider/model call, no network, no telemetry, system fonts only — it only **reads** the reports directory (`AEGIS_REPORTS_DIR`, default `../reports`).
- **Tested.** A pure, null-safe parsing layer (`dashboard/lib/parse/`) turns each report into a typed view-model (status preserved, absent first-class) — unit-tested with Vitest; a CI `dashboard` job runs Biome + `tsc` + Vitest + `next build` fully offline.

```bash
cd dashboard && npm ci && npm run dev   # http://localhost:3000 — reads ../reports
```

> `dashboard/fixtures/` is **SAMPLE data for unit tests only — NOT real Aegis results**; the dashboard at runtime always reads the real `reports/` directory.

---

---

[← back to the README](../README.md)
