# dashboard/fixtures

**SAMPLE data for unit tests only — NOT real Aegis results.**

These `sample-*.json` files are hand-authored, shape-faithful examples of the report
JSON the Python side writes (`reports/eval-*.json`, `redteam-*.json`,
`calibration.json`, `evidence-*.json`). They exist solely so the pure parsers in
`lib/parse/` can be unit-tested without a live system.

The dashboard at **runtime always reads the real `reports/` directory** (see
`lib/reports.ts`); it never reads these fixtures. The numbers here are illustrative,
not measurements produced by Aegis.
