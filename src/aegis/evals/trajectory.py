"""Shared trajectory matching primitives.

``match_trajectory`` is the order-insensitive two-pass matcher originally inlined
in the L3 scorer: pass 1 consumes exact (name + args) matches, pass 2 pairs any
remaining same-name calls as wrong-args. Both the L3 scorer and the F4
ToolCorrectness metric build on it, so the matching logic lives in exactly one
place. Args are compared by value (dict equality); ``status`` (a call OUTCOME) is
intentionally NOT part of step identity here.
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis.evals.models import ToolCall


@dataclass(frozen=True, slots=True)
class MatchCounts:
    """Outcome of matching an actual trajectory against the expected one."""

    exact: int  # calls matching expected by name AND args
    wrong_args: int  # right tool, wrong args
    missing: int  # expected calls with no actual counterpart
    extra: int  # actual calls beyond what was expected
    len_expected: int
    len_actual: int

    def tool_f1(self) -> float:
        """F1 of exact (name+args) matches. Both sides empty is vacuously 1.0;
        exactly one side empty is 0.0 (all missing or all extra)."""
        if not self.len_expected and not self.len_actual:
            return 1.0
        if not self.len_expected or not self.len_actual:
            return 0.0
        precision = self.exact / self.len_actual
        recall = self.exact / self.len_expected
        return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def match_trajectory(expected: list[ToolCall], actual: list[ToolCall]) -> MatchCounts:
    """Two-pass, order-insensitive match of ``actual`` against ``expected``."""
    exp_matched = [False] * len(expected)
    act_used = [False] * len(actual)

    # pass 1: exact (name + args) matches
    for i, e in enumerate(expected):
        for j, a in enumerate(actual):
            if not act_used[j] and a.name == e.name and a.arguments == e.arguments:
                exp_matched[i] = True
                act_used[j] = True
                break

    # pass 2: remaining same-name calls -> wrong args
    wrong_args = 0
    for i, e in enumerate(expected):
        if exp_matched[i]:
            continue
        for j, a in enumerate(actual):
            if not act_used[j] and a.name == e.name:
                act_used[j] = True
                wrong_args += 1
                break

    exact = sum(exp_matched)
    missing = len(expected) - exact - wrong_args
    extra = len(actual) - exact - wrong_args
    return MatchCounts(exact, wrong_args, missing, extra, len(expected), len(actual))
