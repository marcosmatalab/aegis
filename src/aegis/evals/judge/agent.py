"""Agent-as-a-Judge — evaluates the TRAJECTORY (process), not just the output.

It reuses F3's judge PATTERN (an async ABC + a frozen verdict + a deterministic
mock + a clearly-stubbed real backend) but NOT F3's ``Judge`` interface, whose
``score(criteria, output, ...)`` signature is output-centric and does not fit a
trajectory.

HONESTY: ``MockTrajectoryJudge`` is an ILLUSTRATIVE HEURISTIC, not a semantic
judge. It flags loops and redundant steps by literal pattern matching over the
recorded calls (same (name,args) repeated/cycled) and infers error recovery from
the ``status`` field — it does NOT understand whether a step was *reasonable*.
Its penalty weights are arbitrary and fixed so tests can assert exact numbers.
This mirrors F3's honesty about the lexical mock judge: the value is a
regression-catching signal, not ground truth. The real ``agent`` backend (a
reasoning LLM) is a clear stub here, wired in a later phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aegis.evals.judge.geval import JudgeNotConfiguredError
from aegis.evals.models import EvalCase
from aegis.gateway.config import Settings

# Fixed, illustrative penalty weights (see module docstring).
_LOOP_PENALTY = 0.5
_REDUNDANT_PENALTY = 0.2
_REDUNDANT_CAP = 0.6
_UNRECOVERED_ERROR_PENALTY = 0.3
_RECOVERED_ERROR_PENALTY = 0.1


@dataclass(frozen=True, slots=True)
class TrajectoryVerdict:
    score: float  # 0..1
    reasoning: str
    findings: tuple[str, ...] = ()
    has_loop: bool = False
    redundant_steps: int = 0
    recovered_from_error: bool | None = None  # None = no error signal in the trajectory
    judge: str = ""


class TrajectoryJudge(ABC):
    name: str

    @abstractmethod
    async def assess(self, case: EvalCase) -> TrajectoryVerdict: ...

    async def aclose(self) -> None:
        """Release any held resources on shutdown. No-op by default; the keyless
        ``MockTrajectoryJudge`` inherits this unchanged."""
        return None


def _detect_loop(steps: list[tuple]) -> bool:
    """A loop = the same call back-to-back, or a repeated adjacent A->B->A->B cycle."""
    consecutive = any(steps[i] == steps[i + 1] for i in range(len(steps) - 1))
    bigram_cycle = any(steps[i : i + 2] == steps[i + 2 : i + 4] for i in range(len(steps) - 3))
    return consecutive or bigram_cycle


def _count_redundant(steps: list[tuple]) -> int:
    """Number of calls that exactly repeat an earlier call (same name+args)."""
    seen: list[tuple] = []
    redundant = 0
    for s in steps:
        if s in seen:
            redundant += 1
        else:
            seen.append(s)
    return redundant


def _error_recovery(case: EvalCase) -> bool | None:
    """True/False if any errored call was/wasn't later retried successfully on the
    same tool; None if the trajectory carries no error status at all."""
    calls = case.actual.tool_calls
    if not any(c.status == "error" for c in calls):
        return None
    for i, c in enumerate(calls):
        if c.status == "error" and any(
            later.name == c.name and later.status == "ok" for later in calls[i + 1 :]
        ):
            return True
    return False


class MockTrajectoryJudge(TrajectoryJudge):
    name = "mock-trajectory"

    async def assess(self, case: EvalCase) -> TrajectoryVerdict:
        calls = case.actual.tool_calls
        steps = [(c.name, c.arguments) for c in calls]

        if not steps:
            return TrajectoryVerdict(
                1.0, "no tool calls — trajectory trivially clean", (), judge=self.name
            )

        has_loop = _detect_loop(steps)
        redundant = _count_redundant(steps)
        recovered = _error_recovery(case)

        score = 1.0
        findings: list[str] = []
        if has_loop:
            score -= _LOOP_PENALTY
            findings.append("loop detected (a call repeats back-to-back or cycles)")
        if redundant:
            score -= min(_REDUNDANT_PENALTY * redundant, _REDUNDANT_CAP)
            findings.append(f"{redundant} redundant step(s) repeat an earlier call")
        if recovered is False:
            score -= _UNRECOVERED_ERROR_PENALTY
            findings.append("an errored call was not recovered")
        elif recovered is True:
            score -= _RECOVERED_ERROR_PENALTY
            findings.append("recovered from an errored call via a later retry")

        score = max(0.0, min(1.0, score))
        reasoning = "clean trajectory" if not findings else "; ".join(findings)
        return TrajectoryVerdict(
            score,
            reasoning,
            tuple(findings),
            has_loop=has_loop,
            redundant_steps=redundant,
            recovered_from_error=recovered,
            judge=self.name,
        )


def build_trajectory_prompt(case: EvalCase) -> str:
    """Render the recorded trajectory for a reasoning judge (used by the stub)."""
    lines = [
        f"{i + 1}. {c.name}({c.arguments}) -> {c.status}"
        for i, c in enumerate(case.actual.tool_calls)
    ]
    trajectory = "\n".join(lines) or "(no tool calls)"
    return (
        f"Goal: {case.user_goal}\n"
        f"Trajectory:\n{trajectory}\n\n"
        "Assess the PROCESS: loops, redundant steps, error recovery. "
        'Reply JSON {"reasoning": ..., "score": 0..1}.'
    )


class AgentJudge(TrajectoryJudge):
    """Real reasoning-LLM trajectory judge — a clear stub in F4 (no SDK imported)."""

    name = "agent"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def assess(self, case: EvalCase) -> TrajectoryVerdict:
        _ = build_trajectory_prompt(case)  # prompt building works; no provider is wired
        raise JudgeNotConfiguredError(
            "The Agent-as-a-Judge needs a real LLM provider, which is not wired in F4. "
            "Set AEGIS_AGENT_JUDGE_BACKEND=mock to assess trajectories offline."
        )


def build_trajectory_judge(settings: Settings) -> TrajectoryJudge:
    """Select the trajectory judge from settings (mirrors the L2 judge factory)."""
    backend = settings.agent_judge_backend
    if backend == "mock":
        return MockTrajectoryJudge()
    if backend == "agent":
        return AgentJudge(settings)
    raise ValueError(f"unknown agent-judge backend {backend!r}")
