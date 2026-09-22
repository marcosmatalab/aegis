# Frozen artifacts

Everything in this directory is **committed evidence for a number that appears in the
README**. Nothing here is generated at test time and nothing here is gitignored — that is
the whole point. `reports/` (gitignored) is where a *local* run writes; `artifacts/` is
where a run that someone else has to be able to check is *frozen*.

---

## `calibration-geval-2026-09-22.jsonl` — the judge-vs-human agreement run

The per-case verdicts behind the README's headline **Cohen's kappa 0.933**.

| | |
|---|---|
| Judge backend | `geval` (G-Eval style, single judge, JSON verdict) |
| Model | `anthropic/claude-opus-4-8` |
| Temperature | `0.0` |
| `max_tokens` | `1024` |
| Dataset | `src/aegis/evals/datasets/calibration.jsonl`, sha256 `e0fc2f00…3ae38b1` |
| Cases | 30 (15 relevancy, 15 faithfulness) |
| Parse failures | **0** |
| Pass threshold | `0.5` (score `>= 0.5` binarizes to `pass`) |
| Run date | 2026-09-22 |
| Wall time | ~57 s (30 sequential calls) |

### Recompute it yourself, offline

No API key, no `[anthropic]` extra, no network:

```bash
aegis calibrate --from-verdicts artifacts/calibration-geval-2026-09-22.jsonl
```

```
relevancy:    kappa=0.865 p_o=0.933 n_valid=15 parse_failed=0 band=almost perfect
faithfulness: kappa=1.000 p_o=1.000 n_valid=15 parse_failed=0 band=almost perfect
global:       kappa=0.933 p_o=0.967 n_valid=30 parse_failed=0 band=almost perfect
```

`tests/test_evals_calibration_artifact.py` asserts those three numbers against this file on
every CI run, so the artifact and the README cannot drift apart silently.

### Why this file is frozen on purpose

> These verdicts are frozen on purpose. The judge model will eventually be retired, and when
> it is, the "run it with your own key" path stops reproducing. This file is then the only
> durable evidence of that number.

Regenerating it is a deliberate act, not a routine one:

```bash
pip install -e ".[dev,anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
aegis calibrate --judge geval \
  --dump-verdicts artifacts/calibration-geval-$(date +%Y-%m-%d).jsonl \
  --output       artifacts/calibration-geval-$(date +%Y-%m-%d).json
```

A regenerated run gets a **new dated pair of files** and an updated test. The old pair stays,
because deleting the evidence for a number the README used to quote would defeat the purpose.

### Format

JSONL. Line 1 is a `meta` record (judge, model, date, threshold, dataset sha256, case count).
Every later line is a `verdict` record carrying both sides of one judgment: the case text and
the **human** label, and the **judge**'s score, reasoning and parse status. The file is
self-contained — you can read one line and see exactly what was judged and how — and the
`dataset_sha256` plus the id/label cross-check in the loader make drift from
`calibration.jsonl` loud instead of silent.

### The one disagreement, now recoverable

13 pass/pass, 16 fail/fail, 0 false negatives, **1 false positive** (`human=fail`,
`judge=pass`). Earlier versions of the README said the specific case was not recoverable from
the run. It is now:

- **`cal-rel-05`** — reference: *"The Great Wall of China is over 13,000 miles long."*
  Output: *"The Great Wall of China is over 13,000 miles long **and is visible from the Moon
  with the naked eye**."*
- The judge scored it **exactly `0.5`**, and its reasoning names the problem correctly:
  *"adds a false claim that it's visible from the Moon with the naked eye, which is
  inconsistent/inaccurate."*

So the sole disagreement is not a comprehension failure. The judge understood the case and
expressed it as a *partial* score, which the `>= 0.5` binarization then rounds **toward
pass**. That is a property of collapsing a graded score into two categories at a boundary,
and it is the kind of thing that only becomes visible once the per-case verdicts are kept.

### How to read this number honestly

N=30, a **single annotator** (the author), and a calibration set written in the same model
family as the judge. It is a directional signal with a wide interval, not a verdict on the
judge. See [`docs/evals.md`](../docs/evals.md) for the full caveats.

---

## `calibration-geval-2026-09-22.json`

The aggregate report from that same run: per-criterion and global kappa, `p_o`, `p_e`,
`n_valid`, the Landis-Koch band, and the named confusion-matrix cells. It is what
`--from-verdicts` regenerates, so it is also a checksum on the recompute path.
