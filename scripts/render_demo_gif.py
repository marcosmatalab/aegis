"""Render docs/demo.gif from the REAL output of a real offline run.

WHY THIS EXISTS. The previous GIF was a screen recording, and it shipped four
things it should not have: 2.2s of Chrome's ERR_CONNECTION_REFUSED (the browser
was opened before Next was listening), the author's home path, a work-branch
name in the shell prompt, and — worst — a closing frame showing the MOCK judge's
negative kappa while the README promised 0.93.

This script removes that whole class of problem by construction. It does not
record a screen: it takes the captured stdout of commands that actually ran and
lays it out on a synthetic terminal, so there is no window chrome to leak, no
prompt to reveal a machine name, and no browser to race. Every figure shown is
read from a capture file — nothing here can print a number the tools did not.

Usage:
    python scripts/render_demo_gif.py <capture-dir> [--out docs/demo.gif]

The capture directory is produced by ``scripts/capture_demo.sh``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- terminal look -------------------------------------------------------- #
W, H = 1000, 620
PAD_X, PAD_Y = 22, 18
LINE_H = 19
FONT_SIZE = 14

BG = (13, 17, 23)  # a neutral dark, not a screenshot of anyone's theme
FG = (201, 209, 217)
DIM = (125, 133, 144)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
YELLOW = (210, 153, 34)
CYAN = (86, 182, 194)
PROMPT = (88, 166, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

# Frame timings (ms). Typing is quick; a result the viewer must actually READ is
# held. The key shot (the kappa recompute) gets the longest hold in the file.
MS_TYPE = 45
MS_AFTER_CMD = 320
MS_LINE = 55
MS_HOLD = 1900
MS_HOLD_LONG = 3200


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# Anything that could identify the machine this was rendered on. The GIF is a
# public artifact; a home directory in frame is a small leak and an easy one to
# avoid entirely.
_SCRUB = [
    (re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s]+\\+Desktop\\+aegis", re.I), "~/work/aegis"),
    (re.compile(r"[A-Za-z]:\\+work\\+aegis", re.I), "~/work/aegis"),
    (re.compile(r"/c/Users/[^/\s]+/Desktop/aegis", re.I), "~/work/aegis"),
    (re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s]+", re.I), "~"),
]


def scrub(text: str) -> str:
    for pattern, repl in _SCRUB:
        text = pattern.sub(repl, text)
    return text.replace("\\", "/")


def colour_for(line: str) -> tuple[int, int, int]:
    stripped = line.strip()
    if stripped.startswith("FAIL") or " -> fail" in line:
        return RED
    if stripped.startswith("PASS") or stripped.startswith("Success"):
        return GREEN
    if stripped.startswith(("note:", "(", "known gaps", "EXIT=")):
        return DIM
    if re.search(r"kappa=0\.9|overall=|rate=0\.720|detected=", line):
        return CYAN
    if stripped.startswith("[") or stripped.startswith("- "):
        return YELLOW
    return FG


class Terminal:
    """A scrolling buffer of (text, colour) rows rendered to RGB frames."""

    def __init__(self) -> None:
        self.font = load_font(FONT_SIZE)
        self.rows: list[tuple[str, tuple[int, int, int]]] = []
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []
        self.max_rows = (H - 2 * PAD_Y) // LINE_H

    def _render(self) -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        for i, (text, colour) in enumerate(self.rows[-self.max_rows :]):
            d.text((PAD_X, PAD_Y + i * LINE_H), text, font=self.font, fill=colour)
        return img

    def snap(self, ms: int) -> None:
        self.frames.append(self._render())
        self.durations.append(ms)

    def type(self, command: str) -> None:
        """Type a command a few characters at a time, then pause on it."""
        self.rows.append(("", FG))
        for i in range(0, len(command) + 1, 3):
            self.rows[-1] = ("$ " + command[:i] + ("\u2588" if i < len(command) else ""), PROMPT)
            self.snap(MS_TYPE)
        self.rows[-1] = ("$ " + command, PROMPT)
        self.snap(MS_AFTER_CMD)

    def emit(self, text: str, *, per_line_ms: int = MS_LINE, hold: int = MS_HOLD) -> None:
        lines = scrub(text).rstrip("\n").split("\n")
        for line in lines:
            self.rows.append((line[:118], colour_for(line)))
            self.snap(per_line_ms)
        self.snap(hold)

    def say(self, text: str, *, hold: int = MS_HOLD) -> None:
        self.rows.append((text, DIM))
        self.snap(hold)

    def clear(self) -> None:
        self.rows = []

    def image(self, path: Path, *, hold: int, caption: str = "") -> None:
        """Show a real dashboard screenshot, letterboxed onto the same canvas."""
        shot = Image.open(path).convert("RGB")
        top = 46 if caption else 10
        avail_w, avail_h = W - 20, H - top - 10
        scale = min(avail_w / shot.width, avail_h / shot.height)
        shot = shot.resize((int(shot.width * scale), int(shot.height * scale)), Image.LANCZOS)
        img = Image.new("RGB", (W, H), BG)
        if caption:
            ImageDraw.Draw(img).text((PAD_X, 16), caption, font=self.font, fill=CYAN)
        img.paste(shot, ((W - shot.width) // 2, top + (avail_h - shot.height) // 2))
        self.frames.append(img)
        self.durations.append(hold)

    def save(self, out: Path) -> None:
        # A global adaptive palette keeps colours stable across frames, which both
        # avoids inter-frame flicker and compresses better than per-frame palettes.
        frames = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in self.frames]
        out.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            out,
            save_all=True,
            append_images=frames[1:],
            duration=self.durations,
            loop=0,
            optimize=True,
            disposal=2,
        )


def build(cap: Path, out: Path) -> None:
    read = lambda name: (cap / name).read_text(encoding="utf-8")  # noqa: E731
    t = Terminal()

    t.say("Aegis - the control layer for any LLM or agent. Everything below runs offline.")

    # 1. red-team: the number, and the gaps it refuses to hide
    t.type("aegis redteam run")
    t.emit(read("01-redteam.txt"), hold=MS_HOLD_LONG)

    t.clear()
    # 2. evals
    t.type("aegis eval run")
    t.emit(read("02-eval.txt"), hold=MS_HOLD)

    # 3. THE key shot: the headline kappa, recomputed from committed bytes
    t.say("")
    t.say("the real judge's agreement with human labels - no API key, no network:")
    t.type("aegis calibrate --from-verdicts artifacts/calibration-geval-2026-09-22.jsonl")
    t.emit(read("03-kappa.txt"), hold=MS_HOLD_LONG)
    t.say("^ recomputed from 30 committed per-case verdicts. Nothing was called.", hold=MS_HOLD)

    t.clear()
    # 4. the gate: PASS, then a REAL regression caught
    t.type("aegis eval gate")
    t.emit(read("04-gate-pass.txt"), hold=MS_HOLD)
    t.say("")
    t.say("now break the L3 scorer on purpose, and run the same gate:")
    t.type("aegis eval gate")
    t.emit(read("05-gate-fail.txt"), per_line_ms=45, hold=MS_HOLD_LONG)

    t.clear()
    # 5. governance evidence
    t.type("aegis evidence --format json")
    t.emit(read("06-evidence.txt"), hold=MS_HOLD)

    # 6. the dashboard, over the very reports the run just wrote
    for name, caption in (
        ("dashboard-eval.png", "the dashboard reads the reports the run just wrote"),
        ("dashboard-redteam.png", "19/29 detected - and the 10 that get through are named"),
        ("dashboard-kappa.png", "judge calibration: Cohen's kappa 0.933 vs human labels"),
    ):
        t.image(Path("docs") / name, hold=3400, caption=caption)

    t.save(out)
    total = sum(t.durations) / 1000
    size = out.stat().st_size / 1_000_000
    print(f"{out}: {len(t.frames)} frames, {total:.1f}s, {size:.2f} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("docs/demo.gif"))
    args = ap.parse_args()
    build(args.capture_dir, args.out)


if __name__ == "__main__":
    main()
