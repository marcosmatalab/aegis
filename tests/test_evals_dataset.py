"""Tests for the JSONL golden-dataset loader."""

from __future__ import annotations

import json

import pytest

from aegis.evals.dataset import GoldenDatasetError, load_golden


def _line(case_id, **overrides):
    body = {
        "id": case_id,
        "user_goal": "g",
        "input_messages": [{"role": "user", "content": "hi"}],
        "actual": {"final_output": "ok", "tool_calls": []},
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    body.update(overrides)
    return json.dumps(body)


def _write(tmp_path, lines):
    p = tmp_path / "golden.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def test_loads_valid_cases_and_skips_blank_and_comments(tmp_path):
    p = _write(tmp_path, ["# header comment", "", _line("a"), "   ", _line("b")])
    cases = load_golden(p)
    assert [c.id for c in cases] == ["a", "b"]


def test_malformed_json_line_reports_line_number(tmp_path):
    p = _write(tmp_path, [_line("a"), "{not json"])
    with pytest.raises(GoldenDatasetError, match=r":2:.*invalid JSON"):
        load_golden(p)


def test_invalid_case_reports_field(tmp_path):
    bad = json.dumps({"id": "x", "user_goal": "g"})  # missing required fields
    p = _write(tmp_path, [bad])
    with pytest.raises(GoldenDatasetError, match=r":1:.*invalid case"):
        load_golden(p)


def test_duplicate_id_rejected(tmp_path):
    p = _write(tmp_path, [_line("dup"), _line("dup")])
    with pytest.raises(GoldenDatasetError, match=r"duplicate case id 'dup'"):
        load_golden(p)


def test_empty_dataset_rejected(tmp_path):
    p = _write(tmp_path, ["# only comments", ""])
    with pytest.raises(GoldenDatasetError, match=r"contains no cases"):
        load_golden(p)


def test_synthetic_trace_provenance_loads_fine(tmp_path):
    # explicit synthetic provenance (or none) is the only legal file-authored form
    p = _write(
        tmp_path,
        [_line("a", trace={"latency_ms": 12.0, "cost_usd": 0.001, "latency_source": "synthetic"})],
    )
    cases = load_golden(p)
    assert cases[0].trace.latency_source == "synthetic"


def test_hand_authored_measured_source_is_rejected(tmp_path):
    # a golden line cannot self-declare 'measured' — that is earned only at runtime
    p = _write(tmp_path, [_line("a", trace={"latency_ms": 12.0, "latency_source": "measured"})])
    with pytest.raises(GoldenDatasetError, match=r"must be 'synthetic'.*telemetry bridge"):
        load_golden(p)


def test_hand_authored_estimated_cost_source_is_rejected(tmp_path):
    p = _write(tmp_path, [_line("a", trace={"cost_usd": 0.01, "cost_source": "estimated"})])
    with pytest.raises(GoldenDatasetError, match=r"must be 'synthetic'"):
        load_golden(p)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(GoldenDatasetError, match=r"not found"):
        load_golden(tmp_path / "nope.jsonl")
