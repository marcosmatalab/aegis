"""Pure F8 evidence builder — derive control status from REAL artifact fields.

``build_evidence`` walks the committed mapping and, for each evidenceable control,
computes its status as a FUNCTION of (artifact present, the specific field's real
value). It imports no PDF library and does no I/O — the loader hands it plain dicts +
the effective ``Settings``, so the whole mapping/derivation logic is unit-testable
with fixtures.

Honesty gates baked in here (not in the mapping):
* a missing artifact -> ``not_covered`` with the exact produce-it command, never a
  crash, never a fabricated value;
* eval-derived controls are capped at ``partial`` when ``judge == "mock"`` (L2 came
  from the deterministic heuristic judge, a wiring smoke test — not a real eval);
* calibration kappa that is ``None`` / band ``"undefined"`` (a degenerate agreement
  table) is ``not_covered``, never a stale "almost perfect";
* a ``synthetic``/``placeholder`` CLEAR dimension is carried verbatim, never shown as
  measured;
* the guardrail posture (effective config NOW) and the red-team report are SEPARATE
  controls, each saying so, so neither is mistaken for the other's configuration.
"""

from __future__ import annotations

from collections import Counter

from aegis.evidence.mapping import MAPPING, ControlSpec
from aegis.evidence.models import DISCLAIMER, EvidenceControl, EvidenceReport
from aegis.gateway.config import Settings

# (status, artifact_source, fields_read, derived_value, caveat)
_Derived = tuple[str, str, list[str], str, str]

_MOCK_CAVEAT = (
    "judge=mock: deterministic wiring smoke test (L2 produced by the heuristic judge), "
    "not a real-judge evaluation"
)
_GOLDEN_CAVEAT = "scored over the committed golden set, not the deployment data distribution"


def _is_num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _fmt(x: object) -> str:
    return f"{x:.3f}" if _is_num(x) else "n/a"


def _levels_str(levels: object) -> str:
    levels = levels if isinstance(levels, dict) else {}
    parts = []
    for lvl in ("L1", "L2", "L3"):
        d = levels.get(lvl)
        if isinstance(d, dict):
            parts.append(f"{lvl} {d.get('passed', '?')}/{d.get('scored', '?')}")
    return ", ".join(parts)


def _derive_eval(aspect: str, report: dict | None, judge_is_mock_caveat: str) -> _Derived:
    src = "eval report"
    if report is None:
        return ("not_covered", "—", [], "no eval report found (run: aegis eval run)", "")
    judge = report.get("judge", "")
    is_mock = judge == "mock"
    clear = report.get("clear") or {}
    if aspect == "accuracy":
        acc = clear.get("accuracy") or {}
        value = acc.get("value")
        if not _is_num(value):
            return (
                "not_covered",
                src,
                ["clear.accuracy"],
                "eval report has no usable (numeric) accuracy value",
                "",
            )
        fields = ["clear.accuracy", "overall_score", "levels", "judge"]
        val = (
            f"accuracy={_fmt(value)} ({acc.get('status')}); "
            f"overall={_fmt(report.get('overall_score'))}; "
            f"{_levels_str(report.get('levels', {}))}; judge={judge}"
        )
        status = "partial" if is_mock else "covered"
        caveat = judge_is_mock_caveat if is_mock else _GOLDEN_CAVEAT
        return (status, src, fields, val, caveat)
    if aspect == "reliability":
        rel = clear.get("reliability") or {}
        eff = clear.get("efficiency") or {}
        if not _is_num(rel.get("value")):
            return (
                "not_covered",
                src,
                ["clear.reliability"],
                "eval report has no usable (numeric) reliability value",
                "",
            )
        fields = ["clear.reliability", "clear.efficiency", "judge"]
        val = (
            f"reliability={_fmt(rel.get('value'))} ({rel.get('status')}), "
            f"efficiency={_fmt(eff.get('value'))} ({eff.get('status')})"
        )
        status = "partial" if is_mock else "covered"
        caveat = (
            _MOCK_CAVEAT
            if is_mock
            else "reliability is an end-to-end pass-rate proxy; cross-run flakiness deferred"
        )
        return (status, src, fields, val, caveat)
    # aspect == "vandv"
    fields = ["levels", "overall_score", "case_count", "suite", "judge"]
    if not report.get("levels") and report.get("overall_score") is None:
        return ("not_covered", src, fields, "eval report has no level results / overall score", "")
    val = (
        f"V&V via L1/L2/L3 eval over {report.get('case_count', '?')} cases; "
        f"overall={_fmt(report.get('overall_score'))}; {_levels_str(report.get('levels', {}))}; "
        f"suite={report.get('suite')}"
    )
    status = "partial" if is_mock else "covered"
    caveat = judge_is_mock_caveat if is_mock else _GOLDEN_CAVEAT
    return (status, src, fields, val, caveat)


def _derive_redteam(aspect: str, report: dict | None) -> _Derived:
    src = "red-team report"
    if report is None:
        return ("not_covered", "—", [], "no red-team report found (run: aegis redteam run)", "")
    overall = report.get("overall") or {}
    categories = report.get("categories") or {}
    gaps = report.get("known_gaps") or []
    gap_ids = ", ".join(g.get("id", "?") for g in gaps[:5] if isinstance(g, dict))
    if aspect == "robustness":
        cats = "; ".join(
            f"{c}({(d or {}).get('owasp') or '—'})={(d or {}).get('detection_rate')}"
            for c, d in sorted(categories.items())
        )
        val = (
            f"overall detection={overall.get('detection_rate')} over "
            f"{report.get('case_count', '?')} attacks; {cats}; {len(gaps)} named gaps"
            + (f" [{gap_ids}]" if gap_ids else "")
        )
        caveat = (
            "directional coverage, NOT a pass/fail compliance number; "
            f"{len(gaps)} named gaps deliberately slip through (disclosed, not hidden)"
        )
        return ("covered", src, ["overall.detection_rate", "categories", "known_gaps"], val, caveat)
    # aspect == "safety" (MEASURE 2.6) — only output toxicity + PII categories
    safety_cats = {k: v for k, v in categories.items() if k in {"output_toxicity", "pii_output"}}
    cats = (
        "; ".join(f"{c}={(d or {}).get('detection_rate')}" for c, d in sorted(safety_cats.items()))
        or "n/a"
    )
    val = f"safety-relevant categories: {cats}; {len(gaps)} named gaps"
    caveat = (
        "PARTIAL: only output-toxicity + PII-leak categories are evaluated; broad safety "
        "(self-harm, dangerous capabilities, etc.) is out of scope"
    )
    return ("partial", src, ["categories.output_toxicity", "categories.pii_output"], val, caveat)


def _derive_calibration(report: dict | None) -> _Derived:
    src = "calibration report"
    if report is None:
        return (
            "not_covered",
            "—",
            [],
            "no calibration report found (run: aegis calibrate --judge geval)",
            "",
        )
    g = report.get("global") or {}
    kappa = g.get("kappa")
    band = g.get("band")
    n_valid = g.get("n_valid")
    judge = report.get("judge", "")
    fields = ["global.kappa", "global.band", "global.n_valid", "judge"]
    if kappa is None or band == "undefined":
        # degenerate agreement table (reachable in kappa.py) — not interpretable
        return (
            "not_covered",
            src,
            fields,
            f"calibration kappa undefined: degenerate agreement table (n_valid={n_valid})",
            "",
        )
    val = f"global kappa={_fmt(kappa)} (p_o={g.get('p_o')}, {band}, n={n_valid}), judge={judge}"
    if judge == "mock":
        return (
            "partial",
            src,
            fields,
            val,
            "mock judge: a wiring smoke test, not a real-judge calibration",
        )
    return (
        "covered",
        src,
        fields,
        val,
        "directional agreement with one annotator applying the rubric, not ground truth",
    )


def _derive_settings(aspect: str, settings: Settings) -> _Derived:
    src = "effective Settings"
    if aspect == "posture":
        fields = ["guardrails_enabled", "gr_*"]
        if not settings.guardrails_enabled:
            return (
                "not_covered",
                src,
                fields,
                "guardrails disabled in effective config (set AEGIS_GUARDRAILS_ENABLED=true)",
                "",
            )
        val_caveat = (
            "effective configuration at evidence-generation time — NOT necessarily the "
            "configuration under which the eval/red-team reports were produced"
        )
        val = (
            f"guardrails_enabled=true; injection={_onoff(settings.gr_injection_enabled)}, "
            f"pii_redact_input={_onoff(settings.gr_pii_redact_input)}, "
            f"policy={_onoff(settings.gr_policy_enabled)}"
            f"(deny={len(settings.gr_policy_deny)},allow={len(settings.gr_policy_allow)}), "
            f"output_pii={settings.gr_output_pii_action}, "
            f"toxicity={_onoff(settings.gr_toxicity_enabled)}@{settings.gr_toxicity_threshold}, "
            f"engine={settings.gr_pii_engine}"
        )
        return ("covered", src, fields, val, val_caveat)
    # aspect == "logs" (A.6.2.8) — request event logs via OTel
    fields = ["otel_enabled", "otel_exporter"]
    if not settings.otel_enabled:
        return (
            "not_covered",
            src,
            fields,
            "OTel tracing disabled (set AEGIS_OTEL_ENABLED=true); no request event logs",
            "",
        )
    if settings.otel_exporter == "none":
        # spans are created in-process but exported NOWHERE -> instrumentation, not a
        # recorded/retained event log (which is what A.6.2.8 is about). Honest partial.
        return (
            "partial",
            src,
            fields,
            "OTel enabled but exporter=none: per-request GenAI spans created in-process, "
            "NOT exported or retained",
            "set AEGIS_OTEL_EXPORTER=console/otlp to actually export+retain event logs",
        )
    val = (
        f"OTel tracing enabled (exporter={settings.otel_exporter}); per-request GenAI spans "
        f"exported"
    )
    return (
        "covered",
        src,
        fields,
        val,
        "request-level GenAI spans (metadata only); not full audit logging",
    )


def _onoff(flag: bool) -> str:
    return "on" if flag else "off"


def _derive(
    spec: ControlSpec,
    eval_report: dict | None,
    redteam_report: dict | None,
    calibration_report: dict | None,
    settings: Settings,
) -> _Derived:
    if spec.source == "eval":
        return _derive_eval(spec.aspect, eval_report, _MOCK_CAVEAT)
    if spec.source == "redteam":
        return _derive_redteam(spec.aspect, redteam_report)
    if spec.source == "calibration":
        return _derive_calibration(calibration_report)
    return _derive_settings(spec.aspect, settings)


def build_evidence(
    *,
    eval_report: dict | None,
    redteam_report: dict | None,
    calibration_report: dict | None,
    settings: Settings,
    suite: str = "golden",
    generated: int = 0,
) -> EvidenceReport:
    """Build the evidence report from the real artifacts (any may be ``None``)."""
    controls: list[EvidenceControl] = []
    for spec in MAPPING:
        if spec.out_of_scope:
            controls.append(
                EvidenceControl(
                    framework=spec.framework,
                    control_id=spec.control_id,
                    control_title=spec.control_title,
                    status="out_of_scope",
                    artifact_source="—",
                    fields_read=[],
                    derived_value=spec.scope_note,
                    caveat="",
                    verified_via=spec.verified_via,
                )
            )
            continue
        status, src, fields, val, caveat = _derive(
            spec, eval_report, redteam_report, calibration_report, settings
        )
        controls.append(
            EvidenceControl(
                framework=spec.framework,
                control_id=spec.control_id,
                control_title=spec.control_title,
                status=status,
                artifact_source=src,
                fields_read=fields,
                derived_value=val,
                caveat=caveat,
                verified_via=spec.verified_via,
            )
        )

    counts = Counter(c.status for c in controls)
    return EvidenceReport(
        generated=generated,
        suite=suite,
        disclaimer=DISCLAIMER,
        summary_counts={
            "covered": counts.get("covered", 0),
            "partial": counts.get("partial", 0),
            "not_covered": counts.get("not_covered", 0),
            "out_of_scope": counts.get("out_of_scope", 0),
        },
        inputs_present={
            "eval": eval_report is not None,
            "redteam": redteam_report is not None,
            "calibration": calibration_report is not None,
            "settings": True,
        },
        controls=controls,
    )
