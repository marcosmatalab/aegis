"""Frozen models for the F8 evidence report (mirror evals/report.py: a snapshot
that maps 1:1 to a JSON document).

An ``EvidenceControl`` carries a framework control, its DERIVED status, and the
exact real value the status was derived from — so the PDF/JSON can be audited back
to an artifact field. The renderer only formats these; it computes nothing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

# covered: artifact present AND a first-class real measurement backs the control.
# partial: present + real value, but the control's full intent exceeds what it proves
#          (carries a mandatory caveat).
# not_covered: the backing artifact is absent / the live posture is off — shows the
#          reason + how to produce it. Never fabricated.
# out_of_scope: Aegis structurally cannot evidence this control (the majority).
Status = Literal["covered", "partial", "not_covered", "out_of_scope"]

# Verbatim on the PDF cover + footer + README. The single anti-overclaim guarantee.
DISCLAIMER = (
    "This document is PARTIAL TECHNICAL EVIDENCE auto-generated from Aegis's own test "
    "artifacts. It maps specific technical controls to framework clauses where Aegis "
    "produces real measurements, and is NOT a compliance certificate, conformity "
    "assessment, or claim of full conformance with the EU AI Act, NIST AI RMF, or "
    "ISO/IEC 42001. Aegis maps only the small set of technical controls shown below; "
    "the majority of each framework's underlying clauses are out of scope (bundled into "
    "the aggregate out-of-scope rows), so the control counts are NOT a coverage "
    "percentage. Every value is derived from the named artifact at generation time; "
    "absent artifacts are shown as not-covered."
)


@dataclass(frozen=True, slots=True)
class EvidenceControl:
    framework: str
    control_id: str
    control_title: str
    status: Status
    artifact_source: str  # e.g. "eval-golden.json", "effective Settings", "—"
    fields_read: list[str]
    derived_value: str  # the real value string, OR the not-covered reason — never invented
    caveat: str
    verified_via: str  # provenance of the cited control id/title (auditable, not asserted)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    generated: int  # unix ts, stamped by the CLI at generation time
    suite: str
    disclaimer: str
    summary_counts: dict[str, int]  # {covered, partial, not_covered, out_of_scope}
    inputs_present: dict[str, bool]  # {eval, redteam, calibration, settings}
    controls: list[EvidenceControl] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
