"""Assemble a judge-calibration report from cases + verdicts (pure, no network).

Splits the judgments into ``relevancy``, ``faithfulness``, and a pooled global
scope. For each scope it EXCLUDES parse_failed verdicts BEFORE binarizing — a
parse failure is not a judgment, and its neutral 0.5 would otherwise binarize to
'pass' at the ``>=0.5`` boundary and silently inflate agreement — then counts
them separately and computes Cohen's kappa over the surviving pairs.

``human_label`` (categorical) is the SOLE driver of kappa; ``human_score`` is
never read here. The report carries only machine facts (kappa, p_o, p_e, named
confusion cells, counts, band); the honesty caveats live in the README.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aegis.evals.calibration.kappa import (
    PASS_THRESHOLD,
    KappaResult,
    binarize,
    build_matrix,
    cohen_kappa,
)
from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.judge.base import JudgeVerdict

_CRITERIA = ("relevancy", "faithfulness")


@dataclass(frozen=True, slots=True)
class KappaSection:
    """One scope's agreement: its kappa result plus how many cases it covered
    and how many were excluded as parse failures (n_valid + n_parse_failed ==
    n_cases)."""

    result: KappaResult
    n_cases: int
    n_parse_failed: int

    def to_dict(self) -> dict[str, object]:
        d = self.result.to_dict()
        d["n_cases"] = self.n_cases
        d["n_parse_failed"] = self.n_parse_failed
        return d


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    judge: str
    threshold: float
    created: int
    n_cases: int
    n_parse_failed: int
    global_: KappaSection
    per_criterion: dict[str, KappaSection]

    def to_dict(self) -> dict[str, object]:
        return {
            "judge": self.judge,
            "threshold": self.threshold,
            "created": self.created,
            "n_cases": self.n_cases,
            "n_parse_failed": self.n_parse_failed,
            # dataclass field is global_ (keyword), JSON key is the clean "global"
            "global": self.global_.to_dict(),
            "per_criterion": {k: v.to_dict() for k, v in self.per_criterion.items()},
        }


def _section(
    cases: Sequence[CalibrationCase], verdicts: Sequence[JudgeVerdict], threshold: float
) -> KappaSection:
    """Build one scope's section. parse_failed is excluded BEFORE binarize at
    this single choke point; binarize() only ever sees a raw float."""
    pairs = []
    n_parse_failed = 0
    for case, verdict in zip(cases, verdicts, strict=True):
        if verdict.parse_failed:
            n_parse_failed += 1
            continue
        pairs.append((case.human_label, binarize(verdict.score, threshold)))
    return KappaSection(
        result=cohen_kappa(build_matrix(pairs)),
        n_cases=len(cases),
        n_parse_failed=n_parse_failed,
    )


def compute_calibration(
    cases: Sequence[CalibrationCase],
    verdicts: Sequence[JudgeVerdict],
    *,
    judge: str,
    threshold: float = PASS_THRESHOLD,
    created: int = 0,
) -> CalibrationReport:
    """Compute per-criterion + global agreement. ``cases`` and ``verdicts`` are
    aligned 1:1 (verdict[i] is the judgment of case[i]); a length mismatch is an
    error, not a silent truncation."""
    if len(cases) != len(verdicts):
        raise ValueError(f"cases ({len(cases)}) and verdicts ({len(verdicts)}) must align 1:1")

    per_criterion: dict[str, KappaSection] = {}
    for crit in _CRITERIA:
        idx = [i for i, c in enumerate(cases) if c.criterion_type == crit]
        per_criterion[crit] = _section(
            [cases[i] for i in idx], [verdicts[i] for i in idx], threshold
        )

    global_section = _section(list(cases), list(verdicts), threshold)
    return CalibrationReport(
        judge=judge,
        threshold=threshold,
        created=created,
        n_cases=len(cases),
        n_parse_failed=global_section.n_parse_failed,
        global_=global_section,
        per_criterion=per_criterion,
    )
