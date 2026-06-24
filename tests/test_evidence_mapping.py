"""The declarative mapping must be well-formed: every row has a verified id+title +
provenance, evidenceable rows bind to a real (source, aspect), and out-of-scope rows
carry a reason — no orphan or silently-asserted controls."""

from __future__ import annotations

from aegis.evidence.mapping import ASPECTS, FRAMEWORKS, MAPPING, SOURCES
from aegis.evidence.models import DISCLAIMER


def test_every_row_has_framework_id_title_and_provenance():
    for c in MAPPING:
        assert c.framework in FRAMEWORKS, c
        assert c.control_id and c.control_title and c.verified_via, c


def test_evidenceable_rows_bind_to_a_real_source_and_aspect():
    for c in MAPPING:
        if c.out_of_scope:
            continue
        assert c.source in SOURCES, c
        assert c.aspect in ASPECTS, c
        assert not c.scope_note, "evidenceable rows must not carry a scope_note"


def test_out_of_scope_rows_have_a_reason_and_no_artifact_binding():
    oos = [c for c in MAPPING if c.out_of_scope]
    assert oos, "the mapping must explicitly mark out-of-scope controls"
    for c in oos:
        assert c.scope_note, c
        assert c.source == "" and c.aspect == "", c


def test_control_ids_unique_within_each_framework():
    for fw in FRAMEWORKS:
        ids = [c.control_id for c in MAPPING if c.framework == fw]
        assert len(ids) == len(set(ids)), f"duplicate control id in {fw}: {ids}"


def test_each_framework_marks_at_least_one_control_out_of_scope():
    # honesty: the majority is out of scope — at minimum every framework says so once
    for fw in FRAMEWORKS:
        assert any(c.out_of_scope for c in MAPPING if c.framework == fw), fw


def test_nist_coverage_is_measure_only():
    # no GOVERN/MAP/MANAGE control is ever marked evidenceable (no backing artifact)
    for c in MAPPING:
        if c.framework.startswith("NIST") and not c.out_of_scope:
            assert c.control_id.startswith("MEASURE"), c


def test_disclaimer_is_defensibly_worded():
    # the out-of-scope rows are bundled, so in-scope ROWS outnumber out-of-scope rows;
    # the disclaimer must frame the counts as a small mapped set vs the many underlying
    # clauses, NOT claim "the majority of controls" (which the visible counts contradict)
    assert "underlying clauses" in DISCLAIMER
    assert "not a coverage percentage" in DISCLAIMER.lower() or "not a coverage" in DISCLAIMER
    assert "not a compliance certificate" in DISCLAIMER.lower()


def test_nist_provenance_does_not_overclaim_verbatim_titles():
    nist_via = {c.verified_via for c in MAPPING if c.framework.startswith("NIST")}
    for via in nist_via:
        assert "paraphrased" in via  # honest about abbreviated titles
        assert "(verbatim from the Core)" not in via
