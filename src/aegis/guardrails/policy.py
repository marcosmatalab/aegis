"""Configurable allow/deny policy engine.

Rules are case-insensitive regex (from ``gr_policy_deny`` / ``gr_policy_allow``).
An allow rule overrides deny: if any allow rule matches, the text is allowed
regardless of deny rules. A malformed regex degrades to a literal substring
match so a misconfigured rule can never crash the gateway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: str  # "allow" | "deny"
    rule_id: str | None = None


# Degenerate allow rules that match everything would silently nullify the entire
# deny list — a security footgun — so they are ignored.
_CATCH_ALL_ALLOW = {"", ".", ".*", ".+", "^.*$", "^.+$", "(.*)", "(.+)"}


def _matches(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text, re.IGNORECASE) is not None
    except re.error:
        return pattern.lower() in text.lower()


def evaluate(text: str, *, deny: list[str], allow: list[str]) -> PolicyDecision:
    """Allow overrides deny; otherwise the first matching deny rule blocks.

    Catch-all allow rules (e.g. ``.`` / ``.*``) are ignored so a single
    over-broad allow can never turn the whole deny list into a no-op.
    """
    for rule in allow:
        if rule.strip() in _CATCH_ALL_ALLOW:
            continue
        if _matches(rule, text):
            return PolicyDecision("allow")
    for rule in deny:
        if _matches(rule, text):
            return PolicyDecision("deny", rule_id=rule)
    return PolicyDecision("allow")
