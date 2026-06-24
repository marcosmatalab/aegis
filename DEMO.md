# Recording the Aegis demo

[`scripts/demo.sh`](scripts/demo.sh) drives a single, honest, end-to-end pass over the
whole system and finishes on the live dashboard. This guide is how to turn that run into
the GIF embedded in the [README](README.md#demo).

Nothing in the demo is staged: every number is produced live over the keyless deterministic
mock, the gate FAIL is a real regression against a tampered baseline *copy*, and the
dashboard reads the very reports the run just wrote. See the honesty note at the bottom.

## The ten beats

| # | Beat | What it proves |
|---|------|----------------|
| 1 | Gateway + `/health` | the OpenAI-compatible gateway is up (active-wait on liveness) |
| 2 | Drop-in call | point any OpenAI client's `base_url` here — `mock/echo-1` answers |
| 3 | PII redacted | email/phone become `<EMAIL_ADDRESS>`/`<PHONE_NUMBER>` *before* the provider sees them |
| 4 | Injection blocked | an OWASP-LLM01 payload → clean `400 guardrail_blocked` / `prompt_injection`, nothing forwarded |
| 5 | `aegis eval run` | L1/L2/L3 + CLEAR over the golden set → `reports/eval-golden.json` |
| 6 | `aegis calibrate` | judge-vs-human Cohen's κ → `reports/calibration.json` (mock = wiring smoke test) |
| 7 | `aegis eval gate` | PASS vs the committed baseline, then a **tampered baseline copy FAILs** with a named regression |
| 8 | `aegis redteam run` | per-OWASP detection rate + the **named gaps** that get through → `reports/redteam-redteam.json` |
| 9 | `aegis evidence` | governance pack with **derived** control statuses + the partial-coverage disclaimer → `reports/evidence-golden.json` |
| 10 | Dashboard | live over the reports beats 5/6/8/9 just produced — caveats verbatim, missing data shown as absent |

## Prerequisites

```bash
# Python side — the gateway + the aegis CLI
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Node side — the dashboard (Node 20+). The script installs the dashboard's deps on
# first run (see the npm ci note below); you don't need to pre-install them.

# Recording tools
#   asciinema  — record the terminal session   (https://asciinema.org)
#   agg        — render the .cast to an animated GIF (https://github.com/asciinema/agg)
```

## Run it once, un-recorded

```bash
DEMO_SLEEP=0 bash scripts/demo.sh        # flat-out smoke run; exits 0, no orphan processes
```

Then record at a readable pace:

```bash
bash scripts/demo.sh                      # paced (DEMO_SLEEP=2 between beats)
```

Knobs (env): `DEMO_SLEEP` (seconds between beats, default `2`; `0` = no pauses),
`GATEWAY_PORT` (default `8080`), `DASHBOARD_PORT` (default `3000`).

> **First-run `npm ci` (don't think it hung).** The dashboard step runs `npm ci` the
> **first** time only — it downloads packages and can take a minute. Every later run
> reuses `dashboard/node_modules` and skips the install (instant, offline). Delete
> `dashboard/node_modules` to force a clean reinstall. Run the demo once before recording
> so the install is already done and the recorded GIF is quick.

## Record → GIF

```bash
# 1. Record the run. Use a paced run so beats are readable; a wide, short terminal
#    (≈100x30) reads best as a GIF.
asciinema rec demo.cast --overwrite --command "bash scripts/demo.sh"
#    The script ends on "Dashboard live at http://localhost:3000/" and then holds the
#    servers up so you can pan to the browser. Press Ctrl-C to stop recording + servers.

# 2. Render to GIF.
agg --font-size 16 demo.cast docs/demo.gif

# 3. (Optional) the live dashboard is a browser, not a terminal — asciinema can't capture
#    it. Either end the GIF at beat 10 ("Dashboard live …") and add a browser screenshot
#    next to it, or screen-record the browser separately and stitch the two clips.
```

## Embed it

Once `docs/demo.gif` exists, un-comment the placeholder in the README's
[Demo](README.md#demo) section (it ships commented so there's no broken image until the
GIF is recorded):

```markdown
![Aegis end-to-end demo](docs/demo.gif)
```

## Honesty (why this demo is trustworthy)

- **Zero hardcoded numbers.** Eval scores, κ, the red-team detection rate, the evidence
  counts — all are whatever the live run prints over the deterministic mock. Change the
  code and the demo's numbers change with it.
- **The gate FAIL is real.** Beat 7 inflates one real golden case's L2 score in a
  *throwaway copy* of the baseline, then runs the gate against that copy; the fresh mock
  run is a genuine regression and the gate names the case. The committed baseline is never
  modified (verify with `git status`).
- **The dashboard shows only what the pipeline produced.** It reads `reports/` (gitignored,
  rewritten every run), renders each report's caveats verbatim (`judge=mock`, synthetic
  CLEAR Cost/Latency, the red-team gaps, the evidence disclaimer), and shows missing data
  as absent — it never paints a rosier picture than the reports.
