"""Pydantic model for one synthetic red-team attack case (the committed catalog).

An ``AttackCase`` is scored OFFLINE by driving the F2 guardrail pipeline directly
(no model, no network). ``category`` is the closed-set bucket the report counts
by; ``owasp`` is a DERIVED, honest OWASP-LLM-Top-10 (2025) mapping — ``None`` when
the check has no clean OWASP slot (toxicity is content-safety; the policy denylist
is a config-driven content policy, not OWASP LLM06 Excessive Agency).

Honesty is enforced at load time: every ``expected_outcome == "passed"`` row MUST
be flagged ``is_known_gap`` with a ``gap_reason`` — so the detection rate can never
be padded to 100% by quietly dropping a payload the scanners miss.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

Category = Literal[
    "prompt_injection",
    "system_prompt_leak",
    "pii_input",
    "pii_output",
    "output_toxicity",
    "policy_denylist",
]

# Honest OWASP-2025 mapping per bucket; None = no clean OWASP slot (disclosed).
_OWASP_FOR: dict[str, str | None] = {
    "prompt_injection": "LLM01",  # Prompt Injection
    "system_prompt_leak": "LLM07",  # System Prompt Leakage (shares the injection detector)
    "pii_input": "LLM02",  # Sensitive Information Disclosure (input redaction)
    "pii_output": "LLM02",  # Sensitive Information Disclosure (output)
    "output_toxicity": None,  # content-safety; not a clean OWASP-2025 category
    "policy_denylist": None,  # config-driven content policy; NOT OWASP LLM06
}
_INPUT_CATEGORIES = {"prompt_injection", "system_prompt_leak", "pii_input", "policy_denylist"}
_OUTPUT_CATEGORIES = {"pii_output", "output_toxicity"}
# The guardrail codes a blocked attack may carry (from the pipeline).
_BLOCK_CODES = {"prompt_injection", "policy_denied", "toxicity", "pii_leak"}
_OVERLAP_OK = {"LLM01", "LLM02", "LLM07", "ASI01"}


class AttackCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    vector: Literal["input", "output"]
    category: Category
    # role only matters for input vectors; includes the non-scanned roles
    # (system/assistant/developer) so the "injection scans only user/tool" blind
    # spot can be catalogued as a named gap. Matches schemas.ChatMessage roles.
    role: Literal["user", "tool", "system", "assistant", "developer"] = "user"
    payload: str = Field(min_length=1)
    expected_outcome: Literal["blocked", "redacted", "passed"]
    expected_code: str | None = None
    is_known_gap: bool = False
    gap_reason: str | None = None
    overlap: list[str] = Field(default_factory=list)  # disclosed cross-mappings, e.g. ["ASI01"]
    tags: list[str] = Field(default_factory=list)
    description: str = ""

    @property
    def owasp(self) -> str | None:
        """The disclosed OWASP-2025 id for this bucket (None = no clean slot)."""
        return _OWASP_FOR[self.category]

    @model_validator(mode="after")
    def _validate(self) -> AttackCase:
        if not _ID_RE.match(self.id):
            raise ValueError(f"attack id must be slug-shaped ([a-z0-9-]), got {self.id!r}")

        if self.category in _INPUT_CATEGORIES and self.vector != "input":
            raise ValueError(f"category {self.category!r} is an input attack, not {self.vector!r}")
        if self.category in _OUTPUT_CATEGORIES and self.vector != "output":
            raise ValueError(f"category {self.category!r} is an output attack, not {self.vector!r}")
        if self.vector == "output" and self.role != "user":
            raise ValueError("output-vector attacks must keep the default role 'user'")

        if self.expected_outcome == "blocked":
            if self.expected_code not in _BLOCK_CODES:
                raise ValueError(
                    f"a blocked attack needs expected_code in {sorted(_BLOCK_CODES)}, "
                    f"got {self.expected_code!r}"
                )
        elif self.expected_code is not None:
            raise ValueError(f"a {self.expected_outcome!r} attack must not set expected_code")

        # passed <=> known gap (no silent green): every passed payload is a flagged,
        # reasoned scanner blind spot, so the detection rate can't be padded to 100%.
        if self.expected_outcome == "passed" and not self.is_known_gap:
            raise ValueError(
                "a 'passed' attack must be flagged is_known_gap=True with a gap_reason"
            )
        if self.is_known_gap and not (self.expected_outcome == "passed" and self.gap_reason):
            raise ValueError("is_known_gap requires expected_outcome='passed' and a gap_reason")
        if self.gap_reason and not self.is_known_gap:
            raise ValueError("gap_reason is set but is_known_gap is False")

        bad = [o for o in self.overlap if o not in _OVERLAP_OK]
        if bad:
            raise ValueError(f"unknown overlap tags {bad}; allowed: {sorted(_OVERLAP_OK)}")
        return self
