"""The demo GIF is the 60-second pitch, so its defects are pinned as tests.

The previous GIF was a screen recording and shipped four things it should not
have: 2.2 seconds of Chrome's ERR_CONNECTION_REFUSED, the author's home path, a
work-branch name in the prompt, and a closing frame showing the MOCK judge's
NEGATIVE kappa while the README promised 0.93.

It is now rendered by ``scripts/render_demo_gif.py`` from captured real output,
which makes most of that unrepresentable. These tests pin the properties that a
careless re-render could still get wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

GIF = Path(__file__).resolve().parent.parent / "docs" / "demo.gif"
SHOTS = [
    "dashboard-eval.png",
    "dashboard-redteam.png",
    "dashboard-kappa.png",
]

PIL = pytest.importorskip("PIL", reason="Pillow ships with the [dev] extra via fpdf2")
from PIL import Image  # noqa: E402


@pytest.fixture(scope="module")
def gif():
    assert GIF.exists(), f"the demo GIF is missing: {GIF}"
    return Image.open(GIF)


def test_gif_has_no_light_frames(gif):
    """A light frame is, in practice, a browser error page.

    The old GIF had nine of them (frames 150-158): the recording opened the
    dashboard before Next was listening. Everything Aegis renders is dark, so a
    bright frame means something foreign got on screen.
    """
    light = []
    for i in range(gif.n_frames):
        gif.seek(i)
        data = list(gif.convert("RGB").resize((30, 18)).getdata())
        if sum(sum(px) for px in data) / (len(data) * 3) > 200:
            light.append(i)
    assert light == [], f"light frames (probable browser error page): {light}"


def test_gif_is_small_enough_to_load_on_the_readme(gif):
    """7 MB above the fold is a slow first impression."""
    size_mb = GIF.stat().st_size / 1_000_000
    assert size_mb < 8.0, f"demo.gif is {size_mb:.1f} MB"


def test_gif_duration_is_a_readable_length(gif):
    """Long enough to show the gate catching a regression, short enough to watch."""
    total_ms = 0
    for i in range(gif.n_frames):
        gif.seek(i)
        total_ms += gif.info.get("duration", 0)
    seconds = total_ms / 1000
    assert 25 <= seconds <= 75, f"demo.gif runs {seconds:.1f}s"


def test_readme_alt_text_matches_the_real_duration():
    """The alt text used to say '2-minute demo' over a 68-second GIF."""
    readme = (GIF.parent.parent / "README.md").read_text(encoding="utf-8")
    assert "docs/demo.gif" in readme
    assert "2-minute demo" not in readme, "the GIF is not two minutes long"


@pytest.mark.parametrize("name", SHOTS)
def test_dashboard_screenshots_are_committed(name):
    shot = GIF.parent / name
    assert shot.exists(), f"missing dashboard screenshot: {shot}"
    with Image.open(shot) as im:
        assert im.width >= 600, f"{name} is too small to read at {im.size}"
