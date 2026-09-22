"""Serialize / reload the per-case judge verdicts behind a calibration number.

WHY THIS EXISTS. ``aegis calibrate --judge geval`` needs an API key, a network
round-trip and a model that will one day be retired. Everything downstream of the
scoring call is pure: ``compute_calibration(cases, verdicts, ...)`` is a function
over a list of verdicts. So the ONLY non-reproducible part of the headline kappa
is the verdict list itself. Freeze that list to a file and the number becomes
recomputable by anyone, offline, with no key and no SDK — which is the difference
between a README claim and a committed artifact.

FORMAT. One JSON object per line (blank and ``#`` comment lines are skipped, same
as ``calibration.dataset``). Line 1 is the ``meta`` record: which judge, which
model, when, the pass threshold, and the sha256 of the dataset the run scored.
Every later line is a ``verdict`` record that carries BOTH the judge's output
(``judge_score``, ``reasoning``, ``parse_failed``) and a copy of the human side
(``human_label``, plus the case text). The copy is deliberate: the artifact is
self-contained, so a reviewer reads one file and sees the output, the hand label
and the machine score side by side, without cross-referencing the dataset.

DRIFT. A self-contained copy can drift from the dataset it came from. Three
independent guards make that loud rather than silent: ``dataset_sha256`` in the
meta record, a 1:1 id check on load, and a committed test that re-derives the
headline kappa from this file. Editing the labels without regenerating the
artifact breaks CI.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aegis.evals.calibration.kappa import PASS_THRESHOLD
from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.judge.base import JudgeVerdict

FORMAT_VERSION = 1


class VerdictsFileError(ValueError):
    """Raised when a verdicts artifact is missing, malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class VerdictsMeta:
    """Provenance of one frozen calibration run."""

    judge: str
    model: str
    created: int
    threshold: float
    dataset: str
    dataset_sha256: str
    n_cases: int
    format_version: int = FORMAT_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "record": "meta",
            "format_version": self.format_version,
            "judge": self.judge,
            "model": self.model,
            "created": self.created,
            "threshold": self.threshold,
            "dataset": self.dataset,
            "dataset_sha256": self.dataset_sha256,
            "n_cases": self.n_cases,
        }


def dataset_sha256(path: str | Path) -> str:
    """Hash the dataset bytes so a later edit to the labels is detectable.

    Reads bytes (not text) so the digest is independent of newline translation on
    the platform that regenerates the artifact.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump_verdicts(
    cases: Sequence[CalibrationCase],
    verdicts: Sequence[JudgeVerdict],
    *,
    judge: str,
    model: str,
    created: int,
    dataset: str | Path,
    threshold: float = PASS_THRESHOLD,
) -> str:
    """Render ``cases`` + ``verdicts`` as the JSONL text of a frozen run.

    Pure: takes data, returns a string, touches no file except to hash the
    dataset it is told about. ``cases[i]`` and ``verdicts[i]`` must align 1:1 —
    the same invariant ``compute_calibration`` enforces, checked here too so a
    misaligned artifact can never be written in the first place.
    """
    if len(cases) != len(verdicts):
        raise ValueError(f"cases ({len(cases)}) and verdicts ({len(verdicts)}) must align 1:1")

    meta = VerdictsMeta(
        judge=judge,
        model=model,
        created=created,
        threshold=threshold,
        dataset=Path(dataset).name,
        dataset_sha256=dataset_sha256(dataset),
        n_cases=len(cases),
    )

    lines = [json.dumps(meta.to_dict(), ensure_ascii=False, sort_keys=True)]
    for case, verdict in zip(cases, verdicts, strict=True):
        row: dict[str, object] = {
            "record": "verdict",
            "id": case.id,
            "criterion_type": case.criterion_type,
            "criterion": case.criterion,
            "output": case.output,
            "human_label": case.human_label,
            "human_score": case.human_score,
            "judge_score": verdict.score,
            "parse_failed": verdict.parse_failed,
            "reasoning": verdict.reasoning,
        }
        # Exactly one grounding per row, by the CalibrationCase invariant. Emit
        # only the one that is set so the artifact mirrors the dataset shape and
        # reloads cleanly through the same extra="forbid" model.
        if case.reference is not None:
            row["reference"] = case.reference
        if case.context is not None:
            row["context"] = case.context
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines) + "\n"


def write_verdicts(
    path: str | Path,
    cases: Sequence[CalibrationCase],
    verdicts: Sequence[JudgeVerdict],
    *,
    judge: str,
    model: str,
    created: int,
    dataset: str | Path,
    threshold: float = PASS_THRESHOLD,
) -> Path:
    """``dump_verdicts`` to a file, creating parent directories.

    The keywords are spelled out rather than forwarded as ``**kwargs`` so a typo
    in a caller is a type error here, not a silent ``TypeError`` at write time.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump_verdicts(
        cases,
        verdicts,
        judge=judge,
        model=model,
        created=created,
        dataset=dataset,
        threshold=threshold,
    )
    # newline="\n" explicitly: this file is COMMITTED evidence, and the repo pins
    # eol=lf in .gitattributes. Writing it through the platform default would emit
    # CRLF on Windows and make the committed bytes depend on who regenerated it.
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return out


_CASE_FIELDS = (
    "id",
    "criterion_type",
    "criterion",
    "output",
    "reference",
    "context",
    "human_label",
    "human_score",
)


def _parse_meta(path: Path, lineno: int, data: dict) -> VerdictsMeta:
    try:
        return VerdictsMeta(
            judge=str(data["judge"]),
            model=str(data["model"]),
            created=int(data["created"]),
            threshold=float(data["threshold"]),
            dataset=str(data["dataset"]),
            dataset_sha256=str(data["dataset_sha256"]),
            n_cases=int(data["n_cases"]),
            format_version=int(data.get("format_version", FORMAT_VERSION)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise VerdictsFileError(f"{path}:{lineno}: malformed meta record: {exc}") from exc


def load_verdicts(
    path: str | Path,
) -> tuple[VerdictsMeta, list[CalibrationCase], list[JudgeVerdict]]:
    """Load a frozen run back into the exact inputs ``compute_calibration`` takes.

    Offline by construction: no judge is built, no key is read, no network is
    touched. Returns the provenance record alongside the aligned cases and
    verdicts so the caller can print WHICH run it just recomputed — a kappa with
    no model and no date attached is the problem this module exists to fix.
    """
    path = Path(path)
    if not path.exists():
        raise VerdictsFileError(f"verdicts file not found: {path}")

    meta: VerdictsMeta | None = None
    cases: list[CalibrationCase] = []
    verdicts: list[JudgeVerdict] = []
    seen_ids: set[str] = set()

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerdictsFileError(
                f"{path}:{lineno}: invalid JSON ({exc.msg}): {line[:80]!r}"
            ) from exc
        if not isinstance(data, dict):
            raise VerdictsFileError(f"{path}:{lineno}: expected a JSON object, got {type(data)}")

        record = data.get("record")
        if record == "meta":
            if meta is not None:
                raise VerdictsFileError(f"{path}:{lineno}: duplicate meta record")
            if cases:
                raise VerdictsFileError(f"{path}:{lineno}: meta must precede the verdict records")
            meta = _parse_meta(path, lineno, data)
            continue
        if record != "verdict":
            raise VerdictsFileError(
                f"{path}:{lineno}: unknown record type {record!r} (expected 'meta' or 'verdict')"
            )
        if meta is None:
            raise VerdictsFileError(f"{path}:{lineno}: verdict record before the meta record")

        # Rebuild the case through the SAME validated model the dataset uses, so a
        # hand-edited artifact hits every CalibrationCase invariant (grounding
        # exclusivity, label/score consistency, slug-shaped id).
        try:
            case = CalibrationCase.model_validate({k: data[k] for k in _CASE_FIELDS if k in data})
        except Exception as exc:  # pydantic ValidationError, kept narrow by message
            raise VerdictsFileError(f"{path}:{lineno}: invalid case: {exc}") from exc
        if case.id in seen_ids:
            raise VerdictsFileError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)

        try:
            score = float(data["judge_score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VerdictsFileError(f"{path}:{lineno}: missing/invalid 'judge_score'") from exc
        if not 0.0 <= score <= 1.0:
            raise VerdictsFileError(f"{path}:{lineno}: judge_score {score} outside 0..1")

        parse_failed = data.get("parse_failed", False)
        if not isinstance(parse_failed, bool):
            raise VerdictsFileError(f"{path}:{lineno}: 'parse_failed' must be a boolean")

        cases.append(case)
        verdicts.append(
            JudgeVerdict(
                score=score,
                reasoning=str(data.get("reasoning", "")),
                criteria=case.criterion,
                judge=meta.judge,
                parse_failed=parse_failed,
            )
        )

    if meta is None:
        raise VerdictsFileError(f"{path}: contains no meta record")
    if not cases:
        raise VerdictsFileError(f"{path}: contains no verdict records")
    if len(cases) != meta.n_cases:
        raise VerdictsFileError(
            f"{path}: meta declares n_cases={meta.n_cases} but the file holds {len(cases)}"
        )
    return meta, cases, verdicts
