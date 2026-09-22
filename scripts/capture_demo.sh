#!/usr/bin/env bash
# Capture the REAL stdout of the demo commands, for scripts/render_demo_gif.py.
#
# The GIF is rendered from these files, never hand-written, so a figure can only
# appear in the GIF if a tool actually printed it. That is the same rule the demo
# script itself follows (zero hardcoded numbers) applied to the recording.
#
# The gate FAIL beat sabotages the L3 scorer, captures the resulting REAL
# regression, and reverts. The revert is in a trap, so an interrupt mid-run still
# restores the file.
#
# Usage:
#   bash scripts/capture_demo.sh [out-dir]     # default: .demo-capture/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUT="${1:-.demo-capture}"
mkdir -p "$OUT"

if command -v aegis >/dev/null 2>&1; then AEGIS=(aegis); else AEGIS=(python -m aegis.cli); fi

L3="src/aegis/evals/l3_tool.py"
L3_BACKUP="$(mktemp)"
cp "$L3" "$L3_BACKUP"
restore() { cp "$L3_BACKUP" "$L3"; rm -f "$L3_BACKUP"; }
trap restore EXIT INT TERM

# Guardrails on for the evidence beat, matching scripts/demo.sh.
export AEGIS_GUARDRAILS_ENABLED=true
export NO_COLOR=1

echo "1/6 redteam run"
"${AEGIS[@]}" redteam run              > "$OUT/01-redteam.txt"     2>&1
echo "2/6 eval run"
"${AEGIS[@]}" eval run                 > "$OUT/02-eval.txt"        2>&1
echo "3/6 calibrate --from-verdicts"
"${AEGIS[@]}" calibrate --from-verdicts artifacts/calibration-geval-2026-09-22.jsonl \
                                       > "$OUT/03-kappa.txt"       2>&1
echo "4/6 eval gate (PASS)"
"${AEGIS[@]}" eval gate                > "$OUT/04-gate-pass.txt"   2>&1

echo "5/6 eval gate (FAIL, against a deliberately broken L3 scorer)"
python - "$L3" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
marker = "def _lcs_len(a: list[str], b: list[str]) -> int:"
assert marker in s, "the sabotage target moved; update capture_demo.sh"
p.write_text(s.replace(marker, marker + "\n    return 0  # deliberate regression", 1), encoding="utf-8")
PY
set +e
"${AEGIS[@]}" eval gate                > "$OUT/05-gate-fail.txt"   2>&1
code=$?
set -e
printf 'EXIT=%s\n' "$code" >> "$OUT/05-gate-fail.txt"
[ "$code" -eq 1 ] || { echo "expected the gate to exit 1, got $code" >&2; exit 1; }
restore
trap - EXIT INT TERM

echo "6/6 evidence"
"${AEGIS[@]}" evidence --format json   > "$OUT/06-evidence.txt"    2>&1

# Only the first few regressions fit on screen; keep the head plus the count.
python - "$OUT/05-gate-fail.txt" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").rstrip("\n").split("\n")
head, rest, tail = lines[0], lines[1:-1], lines[-1]
if len(rest) > 9:
    hidden = len(rest) - 9
    rest = rest[:9] + [f"  ... and {hidden} more, each named"]
p.write_text("\n".join([head, *rest, tail]) + "\n", encoding="utf-8")
PY

echo
echo "captured to $OUT/ - now render with:"
echo "  python scripts/render_demo_gif.py $OUT"
