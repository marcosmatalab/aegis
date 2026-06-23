"""Pure, network-free Cohen's kappa over a 2x2 pass/fail agreement table.

This is the statistical heart of F5 judge calibration: it measures AGREEMENT
between a hand-labeled set and the judge, never ground truth. The judge stays
DIRECTIONAL (see the README honesty caveats: N=30 wide CI, the kappa paradox,
a single annotator, arbitrary Landis-Koch bands).

Conventions, fixed and documented because Cohen's kappa is SYMMETRIC — a
transposed table yields the SAME kappa, so an axis swap is invisible in the
value and only shows in the fp-vs-fn directional story:
  - rows = HUMAN label, cols = JUDGE label, positive class = "pass"
  - tp = human pass & judge pass;  fn = human pass & judge fail
  - fp = human fail & judge pass;  tn = human fail & judge fail

This module is intentionally ignorant of ``JudgeVerdict`` and ``parse_failed``:
parse failures are excluded one layer up (``compute_calibration``) BEFORE any
pair reaches ``binarize``/``build_matrix`` here, so a neutral 0.5 can never leak
into the table.

Degenerate cases NEVER raise and NEVER fabricate a number:
  - ``n_valid == 0`` (nothing to compare): kappa=None, p_o=None, p_e=None.
  - ``1 - p_e == 0`` (BOTH raters collapsed to the SAME single class, e.g. both
    all-pass): kappa is mathematically undefined (0/0) -> kappa=None, but the
    real p_o (typically 1.0) and p_e=1.0 are still reported. A human-constant /
    judge-split table is NOT degenerate — its kappa is well defined (e.g. 0.0).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Label = Literal["pass", "fail"]

PASS_THRESHOLD = 0.5  # operative L2 threshold: judge score >= 0.5 -> pass


def binarize(score: float, threshold: float = PASS_THRESHOLD) -> Label:
    """Binarize a continuous judge score into a pass/fail label.

    Takes a RAW float (never a ``JudgeVerdict``) by design: a parse_failed
    verdict carries the neutral 0.5, which would binarize to ``pass`` at the
    ``>=`` boundary — so it must be excluded upstream and can never reach here.
    """
    return "pass" if score >= threshold else "fail"


@dataclass(frozen=True, slots=True)
class ConfusionMatrix:
    """2x2 counts; rows=human, cols=judge, positive class 'pass'."""

    tp: int = 0  # human pass & judge pass
    fn: int = 0  # human pass & judge fail
    fp: int = 0  # human fail & judge pass
    tn: int = 0  # human fail & judge fail

    @property
    def n(self) -> int:
        return self.tp + self.fn + self.fp + self.tn

    def to_dict(self) -> dict[str, object]:
        # Named cells + an explicit orientation string so a reader can recompute
        # kappa by hand and read the fp-vs-fn story without transposing the axes.
        return {
            "orientation": "rows=human, cols=judge; positive='pass'",
            "human_pass_judge_pass": self.tp,
            "human_pass_judge_fail": self.fn,
            "human_fail_judge_pass": self.fp,
            "human_fail_judge_fail": self.tn,
        }


@dataclass(frozen=True, slots=True)
class KappaResult:
    """Cohen's kappa plus the raw agreement and matrix it was computed from.

    ``kappa``/``p_o``/``p_e`` are ``None`` (JSON null) when undefined — never a
    fabricated 0.0/1.0 and never NaN (which is not valid JSON). p_o and the
    matrix are reported alongside kappa because kappa is base-rate sensitive
    (the kappa paradox): high agreement can still yield a low or undefined kappa.
    """

    kappa: float | None
    p_o: float | None
    p_e: float | None
    n_valid: int
    matrix: ConfusionMatrix
    band: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kappa": self.kappa,
            "p_o": self.p_o,
            "p_e": self.p_e,
            "n_valid": self.n_valid,
            "band": self.band,
            "confusion_matrix": self.matrix.to_dict(),
        }


def build_matrix(pairs: Iterable[tuple[Label, Label]]) -> ConfusionMatrix:
    """Tabulate ``(human_label, judge_label)`` pairs into a 2x2 matrix.

    Pairs MUST already exclude parse failures (this layer never sees verdicts).
    """
    tp = fn = fp = tn = 0
    for human, judge in pairs:
        if human == "pass":
            if judge == "pass":
                tp += 1
            else:
                fn += 1
        elif judge == "pass":
            fp += 1
        else:
            tn += 1
    return ConfusionMatrix(tp=tp, fn=fn, fp=fp, tn=tn)


def landis_koch_band(kappa: float | None) -> str:
    """Map kappa to its conventional Landis-Koch band.

    The band BOUNDARIES are ARBITRARY conventions (stated in the README), not an
    objective quality verdict. ``None`` maps to 'undefined' rather than being
    coerced into 'poor'/'slight'.
    """
    if kappa is None:
        return "undefined"
    if kappa < 0.0:
        return "poor"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


def cohen_kappa(matrix: ConfusionMatrix) -> KappaResult:
    """Compute Cohen's kappa from a 2x2 matrix; never raises, never fabricates.

    kappa = (p_o - p_e) / (1 - p_e), with p_o the observed agreement and p_e the
    chance agreement from the marginals. Two degenerate guards (see module docs):
    n_valid == 0 -> everything None; 1 - p_e == 0 -> kappa None but p_o/p_e kept.
    """
    n = matrix.n
    if n == 0:
        return KappaResult(None, None, None, 0, matrix, landis_koch_band(None))

    p_o = (matrix.tp + matrix.tn) / n
    human_pass = (matrix.tp + matrix.fn) / n
    human_fail = (matrix.fp + matrix.tn) / n
    judge_pass = (matrix.tp + matrix.fp) / n
    judge_fail = (matrix.fn + matrix.tn) / n
    p_e = human_pass * judge_pass + human_fail * judge_fail

    # Guard ONLY on the computed value. p_e == 1.0 (so 1 - p_e == 0) requires
    # BOTH marginals to saturate to the SAME class (both all-pass or both
    # all-fail), where the products are exactly 1.0*1.0 + 0.0*0.0 == 1.0 in
    # binary float — so the `== 0.0` test is bit-exact and needs no epsilon. A
    # single saturated marginal (human-constant, judge-split) leaves 1 - p_e > 0
    # and a well-defined kappa, which we must NOT discard.
    if 1.0 - p_e == 0.0:
        return KappaResult(None, p_o, p_e, n, matrix, landis_koch_band(None))

    kappa = (p_o - p_e) / (1.0 - p_e)
    return KappaResult(kappa, p_o, p_e, n, matrix, landis_koch_band(kappa))


def kappa_from_pairs(pairs: Iterable[tuple[Label, Label]]) -> KappaResult:
    """Convenience: ``cohen_kappa(build_matrix(pairs))``."""
    return cohen_kappa(build_matrix(pairs))
