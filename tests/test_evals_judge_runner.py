"""Runner ↔ real-judge integration: one event loop for the whole run, judge close
on shutdown (swallowing close errors), and parse_failed surfaced + persisted.
All offline with fake providers — no key, no SDK, no network."""

from __future__ import annotations

import asyncio
import json

import pytest

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.geval import GEvalJudge
from aegis.evals.models import EvalCase
from aegis.evals.persistence import write_report
from aegis.evals.runner import run_suite
from aegis.gateway.config import Settings
from aegis.gateway.schemas import ChatCompletionResponse, Choice, ResponseMessage, Usage


def _judge_response(model: str, content: str) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id="j",
        created=1,
        model=model,
        choices=[
            Choice(
                index=0,
                message=ResponseMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


class _LoopRecordingProvider:
    name = "loop-rec"

    def __init__(self, reply='{"score": 0.9, "reasoning": "ok"}'):
        self.reply = reply
        self.loops: list[int] = []
        self.close_loops: list[int] = []
        self.closed = 0

    async def complete(self, request):
        self.loops.append(id(asyncio.get_running_loop()))
        return _judge_response(request.model, self.reply)

    async def aclose(self):
        self.close_loops.append(id(asyncio.get_running_loop()))
        self.closed += 1


def _l2_case(case_id: str, *, reference: str = "the reference") -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id,
            "user_goal": "g",
            "input_messages": [{"role": "user", "content": "hi"}],
            "expected_trajectory": [],
            "reference_answer": reference,
            "success_criteria": {"must_include": []},
            "actual": {"final_output": "out", "tool_calls": []},
            "expected": {"l1_goal_met": False, "l2_faithful": True, "l3_trajectory_match": True},
        }
    )


def test_all_judge_calls_share_one_loop_and_close_once():
    provider = _LoopRecordingProvider()
    judge = GEvalJudge(Settings(_env_file=None), provider)
    report = run_suite([_l2_case("a"), _l2_case("b")], judge)
    # two cases, one relevancy call each -> two complete() calls, all on ONE loop
    assert len(provider.loops) == 2
    assert len(set(provider.loops)) == 1
    assert provider.closed == 1  # judge closed exactly once on shutdown
    # create AND close happened on the SAME loop (a real httpx client requires this)
    assert provider.close_loops == [provider.loops[0]]
    assert report.levels["L2"].scored == 2


class _CleanScoreCloseRaisesJudge(Judge):
    name = "clean-close-raises"

    async def score(self, criteria, output, *, reference=None, context=None):
        return JudgeVerdict(0.7, "ok", criteria, self.name)

    async def aclose(self):
        raise RuntimeError("close boom")


def test_close_error_on_a_clean_run_does_not_raise():
    # a close failure on an otherwise successful run must be swallowed (logged),
    # never turned into a run failure
    report = run_suite([_l2_case("a")], _CleanScoreCloseRaisesJudge())
    assert report.levels["L2"].scored == 1


class _BoomJudge(Judge):
    name = "boom"

    async def score(self, criteria, output, *, reference=None, context=None):
        raise RuntimeError("scoring boom")

    async def aclose(self):
        raise RuntimeError("close boom")


def test_scoring_error_propagates_and_close_error_is_swallowed():
    # the scoring exception must reach the caller; the aclose error must NOT mask it
    with pytest.raises(RuntimeError, match="scoring boom"):
        run_suite([_l2_case("a")], _BoomJudge())


def test_parse_failure_surfaces_in_breakdown_and_persists(tmp_path):
    judge = GEvalJudge(Settings(_env_file=None), _LoopRecordingProvider(reply="not json at all"))
    report = run_suite([_l2_case("c")], judge)
    breakdown = report.cases[0].l2["breakdown"]
    assert breakdown.get("relevancy_parse_failed") is True
    # and it is in the PERSISTED report JSON (F7 / audit read it from there)
    out = write_report(report, tmp_path / "r.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["cases"][0]["l2"]["breakdown"]["relevancy_parse_failed"] is True
