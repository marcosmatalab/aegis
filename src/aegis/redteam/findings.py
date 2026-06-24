"""Typed red-team findings — the F7-additive seam (no gate built here).

``RedteamFinding`` is structurally identical to ``evals.baseline.Regression``
(``kind`` / ``scope`` / ``detail`` + the same ``__str__``), so a FUTURE
``aegis gate`` umbrella can union ``redteam_findings(...)`` with
``compare_to_baseline(...)`` additively. F6 only RETURNS the list and serializes
it in the report; it builds NO gate, NO baseline, and NO non-zero exit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aegis.redteam.outcome import AttackResult


@dataclass(frozen=True, slots=True)
class RedteamFinding:
    # kind (catalog-oracle, F6): attack_passed | oracle_mismatch
    # kind (gate vs committed baseline, F7 redteam.baseline): attack_now_passing |
    #   detection_downgraded | category_detection_drop | category_dropped |
    #   block_code_changed (informational)
    # (extensible, the structural twin of evals.baseline.Regression)
    kind: str
    scope: str  # "<attack-id> <category>" — always NAMES what was found
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.scope}: {self.detail}"


def redteam_findings(results: Sequence[AttackResult]) -> list[RedteamFinding]:
    """Pure (no I/O, no exit): the gate-relevant findings vs the catalog oracle.

    - ``attack_passed``: the catalog expected this attack to be CAUGHT
      (blocked/redacted) but it was observed to PASS — a real, gate-relevant miss.
      A documented known gap has ``expected_outcome == "passed"``, so it matches
      the oracle and is NOT a finding (it is reported under ``known_gaps``).
    - ``oracle_mismatch``: any OTHER observed != authored outcome/code (catalog
      drift or a guardrail behavior change), e.g. a previously-passing gap that now
      blocks. On a self-consistent committed catalog the list is empty.
    """
    out: list[RedteamFinding] = []
    for r in results:
        scope = f"{r.case.id} {r.case.category}"
        if r.outcome == "passed" and r.case.expected_outcome != "passed":
            out.append(
                RedteamFinding(
                    "attack_passed",
                    scope,
                    f"attack expected {r.case.expected_outcome} but passed undetected",
                )
            )
        elif not r.matches_oracle:
            want = r.case.expected_outcome + (
                f"/{r.case.expected_code}" if r.case.expected_code else ""
            )
            got = r.outcome + (f"/{r.code}" if r.code else "")
            out.append(RedteamFinding("oracle_mismatch", scope, f"expected {want}, observed {got}"))
    return out
