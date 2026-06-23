"""F6 automated red-team: run a committed catalog of synthetic attacks DIRECTLY
against the F2 guardrail pipeline (offline, deterministic, keyless — no model, no
network) and report a per-category detection rate.

It measures coverage of the deterministic regex/lexicon guardrails against THIS
catalog — NOT total security. A passing attack is a surfaced finding, not a hidden
failure; the catalog ships deliberate, named scanner blind spots so the rate is an
honest number below 100%. See the README "Automated red-team (F6)" section.
"""

from aegis.redteam.dataset import DEFAULT_ATTACKS_PATH, AttackDatasetError, load_attacks
from aegis.redteam.findings import RedteamFinding, redteam_findings
from aegis.redteam.models import AttackCase
from aegis.redteam.outcome import AttackResult, classify_result
from aegis.redteam.report import RedTeamReport, build_report
from aegis.redteam.runner import build_redteam_settings, run_redteam

__all__ = [
    "DEFAULT_ATTACKS_PATH",
    "AttackCase",
    "AttackDatasetError",
    "AttackResult",
    "RedTeamReport",
    "RedteamFinding",
    "build_redteam_settings",
    "build_report",
    "classify_result",
    "load_attacks",
    "redteam_findings",
    "run_redteam",
]
