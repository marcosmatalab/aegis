"""A small, illustrative content-policy deny-list used by the red-team run ONLY.

This is NOT a production policy and is NOT read from user/global settings — it is
a frozen, committed fixture so the policy stage is genuinely exercised (an EMPTY
deny-list makes ``policy.evaluate`` inert, which would falsely "pass" every policy
attack). The patterns are deliberately injection-clean so the policy stage — not
injection precedence (which runs first) — is what blocks these payloads.
"""

from __future__ import annotations

REDTEAM_DENY: list[str] = [
    r"\bbioweapon\b",
    r"\bransomware\b",
    r"\bnuclear\s+weapon\b",
]
