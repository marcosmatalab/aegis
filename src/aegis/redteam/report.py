"""Aggregate per-attack results into a per-category red-team report (machine facts).

Two honesty signals per category: ``detection_rate`` (did A guardrail act —
blocked or redacted — over the whole bucket, INCLUDING the named gaps, so it is a
real coverage number) and ``oracle_match_rate`` (did the observed outcome+code
match the catalog's authored expectation — proves the harness reproduces real
pipeline behaviour; 1.0 in a healthy run). The honesty caveats live in the README.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from aegis.redteam.findings import RedteamFinding, redteam_findings
from aegis.redteam.outcome import AttackResult


def _rate(num: int, den: int) -> float:
    return round(num / den, 6) if den else 0.0


@dataclass(frozen=True, slots=True)
class CategoryStat:
    owasp: str | None  # disclosed OWASP-2025 mapping (None = no clean slot)
    total: int
    blocked: int
    redacted: int
    passed: int
    detection_rate: float
    oracle_match_rate: float
    by_code: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "owasp": self.owasp,
            "total": self.total,
            "blocked": self.blocked,
            "redacted": self.redacted,
            "passed": self.passed,
            "detection_rate": self.detection_rate,
            "oracle_match_rate": self.oracle_match_rate,
            "by_code": self.by_code,
        }


@dataclass(frozen=True, slots=True)
class RedTeamReport:
    suite: str
    created: int
    case_count: int
    categories: dict[str, CategoryStat]
    overall_detection_rate: float
    overall_oracle_match_rate: float
    known_gaps: list[dict]
    findings: list[RedteamFinding]

    def to_dict(self) -> dict[str, object]:
        return {
            "suite": self.suite,
            "created": self.created,
            "case_count": self.case_count,
            "categories": {k: v.to_dict() for k, v in self.categories.items()},
            "overall": {
                "detection_rate": self.overall_detection_rate,
                "oracle_match_rate": self.overall_oracle_match_rate,
            },
            "known_gaps": self.known_gaps,
            "findings": [
                {"kind": f.kind, "scope": f.scope, "detail": f.detail} for f in self.findings
            ],
        }


def build_report(
    results: Sequence[AttackResult], *, suite: str = "redteam", created: int = 0
) -> RedTeamReport:
    by_cat: dict[str, list[AttackResult]] = {}
    for r in results:
        by_cat.setdefault(r.case.category, []).append(r)

    categories: dict[str, CategoryStat] = {}
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        blocked = sum(r.outcome == "blocked" for r in rs)
        redacted = sum(r.outcome == "redacted" for r in rs)
        passed = sum(r.outcome == "passed" for r in rs)
        codes = Counter(r.code for r in rs if r.outcome == "blocked" and r.code)
        categories[cat] = CategoryStat(
            owasp=rs[0].case.owasp,
            total=len(rs),
            blocked=blocked,
            redacted=redacted,
            passed=passed,
            detection_rate=_rate(blocked + redacted, len(rs)),
            oracle_match_rate=_rate(sum(r.matches_oracle for r in rs), len(rs)),
            by_code=dict(sorted(codes.items())),
        )

    total = len(results)
    detected = sum(r.detected for r in results)
    matched = sum(r.matches_oracle for r in results)
    known_gaps = [
        {
            "id": r.case.id,
            "category": r.case.category,
            "owasp": r.case.owasp,
            "gap_reason": r.case.gap_reason,
        }
        for r in results
        if r.case.is_known_gap
    ]
    return RedTeamReport(
        suite=suite,
        created=created,
        case_count=total,
        categories=categories,
        overall_detection_rate=_rate(detected, total),
        overall_oracle_match_rate=_rate(matched, total),
        known_gaps=known_gaps,
        findings=redteam_findings(results),
    )
