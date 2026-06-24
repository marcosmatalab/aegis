"""The committed, declarative framework-control mapping (F8).

This is the ONLY place control identifiers live. Each row names a framework control,
its provenance (``verified_via``), and — for the controls Aegis CAN evidence — which
real artifact + aspect backs it. The STATUS is never set here; the builder derives it
from the actual artifact at generation time.

Honesty: Aegis maps only a few technical controls; the majority of each framework's
underlying clauses are ``out_of_scope`` (bundled into one aggregate row per framework,
so the control counts are not a coverage percentage). Control ids/titles are cited with
their source; NIST ids are verbatim but titles are abbreviated; ISO/IEC 42001 is
paywalled, so its Annex A ids/titles are paraphrased from secondary listings (noted in
``verified_via``), never quoted as if from the standard.
"""

from __future__ import annotations

from dataclasses import dataclass

EU_AI_ACT = "EU AI Act (Reg. (EU) 2024/1689)"
NIST_RMF = "NIST AI RMF 1.0 (AI 100-1)"
ISO_42001 = "ISO/IEC 42001:2023"

FRAMEWORKS = (EU_AI_ACT, NIST_RMF, ISO_42001)

# Evidenceable controls bind to one (source, aspect); the builder has a deriver per pair.
SOURCES = frozenset({"eval", "redteam", "calibration", "settings"})
ASPECTS = frozenset(
    {"accuracy", "reliability", "vandv", "robustness", "safety", "validity", "posture", "logs"}
)

_NIST_VIA = (
    "NIST AI RMF 1.0 (AI 100-1, Jan 2023), MEASURE function "
    "(id verbatim; title abbreviated/paraphrased from the Core)"
)
_EU_VIA = "Reg. (EU) 2024/1689 Article 15; paragraph numbering via artificialintelligenceact.eu"
_ISO_VIA = (
    "ISO/IEC 42001:2023 Annex A (id+title paraphrased from a public listing; standard is paywalled)"
)


@dataclass(frozen=True, slots=True)
class ControlSpec:
    framework: str
    control_id: str
    control_title: str
    verified_via: str
    source: str = ""  # "" for out_of_scope rows
    aspect: str = ""  # "" for out_of_scope rows
    out_of_scope: bool = False
    scope_note: str = ""  # the (non-claim) reason shown for out_of_scope rows


MAPPING: tuple[ControlSpec, ...] = (
    # --- EU AI Act, Article 15 (accuracy, robustness, cybersecurity) ---------- #
    ControlSpec(
        EU_AI_ACT,
        "Article 15(1)/(3)",
        "Accuracy and declared accuracy metrics",
        _EU_VIA,
        source="eval",
        aspect="accuracy",
    ),
    ControlSpec(
        EU_AI_ACT,
        "Article 15(4)",
        "Robustness (resilience incl. adversarial inputs)",
        _EU_VIA,
        source="redteam",
        aspect="robustness",
    ),
    ControlSpec(
        EU_AI_ACT,
        "Article 15(5)",
        "Cybersecurity (resilience to attempts to alter use/outputs)",
        _EU_VIA,
        source="settings",
        aspect="posture",
    ),
    ControlSpec(
        EU_AI_ACT,
        "Articles 9/10/12/13/14",
        "Risk mgmt, data governance, logging, transparency, human oversight",
        _EU_VIA,
        out_of_scope=True,
        scope_note=(
            "Out of scope: Aegis is a gateway + eval layer, not the model lifecycle / "
            "management system these articles require."
        ),
    ),
    # --- NIST AI RMF 1.0 — MEASURE only --------------------------------------- #
    ControlSpec(
        NIST_RMF,
        "MEASURE 2.3",
        "AI system performance measured and documented",
        _NIST_VIA,
        source="eval",
        aspect="accuracy",
    ),
    ControlSpec(
        NIST_RMF,
        "MEASURE 2.5",
        "AI system demonstrated to be valid and reliable",
        _NIST_VIA,
        source="eval",
        aspect="reliability",
    ),
    ControlSpec(
        NIST_RMF,
        "MEASURE 2.6",
        "AI system evaluated for safety; fails safely",
        _NIST_VIA,
        source="redteam",
        aspect="safety",
    ),
    ControlSpec(
        NIST_RMF,
        "MEASURE 2.7",
        "AI system security and resilience evaluated and documented",
        _NIST_VIA,
        source="redteam",
        aspect="robustness",
    ),
    ControlSpec(
        NIST_RMF,
        "MEASURE 2.13",
        "Effectiveness of the employed TEVV metrics evaluated",
        _NIST_VIA,
        source="calibration",
        aspect="validity",
    ),
    ControlSpec(
        NIST_RMF,
        "GOVERN / MAP / MANAGE",
        "Organizational governance, context mapping, risk treatment",
        _NIST_VIA,
        out_of_scope=True,
        scope_note=(
            "Out of scope: these functions are an organizational program, not something "
            "a gateway can evidence."
        ),
    ),
    # --- ISO/IEC 42001:2023 Annex A ------------------------------------------- #
    ControlSpec(
        ISO_42001,
        "A.6.2.4",
        "AI system verification and validation",
        _ISO_VIA,
        source="eval",
        aspect="vandv",
    ),
    ControlSpec(
        ISO_42001,
        "A.6.2.6",
        "AI system operation and monitoring",
        _ISO_VIA,
        source="settings",
        aspect="posture",
    ),
    ControlSpec(
        ISO_42001,
        "A.6.2.8",
        "AI system recording of event logs",
        _ISO_VIA,
        source="settings",
        aspect="logs",
    ),
    ControlSpec(
        ISO_42001,
        "A.2–A.5, A.7–A.10",
        "Policies, org roles, resources, impact assessment, data, use, third parties",
        _ISO_VIA,
        out_of_scope=True,
        scope_note="Out of scope: AI management-system controls; Aegis is not an AIMS.",
    ),
)
