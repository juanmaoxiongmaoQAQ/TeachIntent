"""Offline diagnostic runner (judge-injected; never calls an API on its own).

Runs each diagnostic pair's ``reference_plan`` and ``degraded_plan`` through
the frozen Evaluator v0.1 (``evaluate_speech_plan``), independently, for a
configurable number of repeats. The judge backend is injected by the caller —
this module performs no network I/O.

Every plan is evaluated with the SAME frozen condition: Evaluator v0.1, Judge
Prompt v0.1, temperature 0, structured output disabled, no retry, no
self-repair. Only the pair's ``input`` and one plan reach the Evaluator;
experiment metadata (``family``, ``target_dimensions``, ``expected_flags``,
``notes``, ``pair_id``) is never passed to the judge.

``run_diagnostic_dry`` validates the dataset and returns an empty run manifest
without any judge call — used to sanity-check the dataset before a real run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ..evaluator import (
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    JudgeCompleter,
    JudgeConfig,
    EvaluationRunContext,
    evaluate_speech_plan,
    compute_judge_prompt_sha256,
)
from .dataset import load_diagnostic_pairs, validate_diagnostic_dataset
from .metrics import EvaluationRecord

__all__ = [
    "DiagnosticRunResult",
    "build_judge_config",
    "build_run_context",
    "run_diagnostic",
    "run_diagnostic_dry",
]

GENERATOR_VERSION = "v0.1"
PROMPT_VERSION = "v0.1"


def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_run_context(pair_id: str) -> EvaluationRunContext:
    """Build the per-run EvaluationRunContext.

    ``input_case_id`` is set to the pair_id. This provenance is experiment
    metadata and never reaches the judge (the Evaluator's sanitizer excludes it).
    """
    return EvaluationRunContext(
        input_case_id=pair_id,
        generator_version=GENERATOR_VERSION,
        prompt_version=PROMPT_VERSION,
    )


def build_judge_config(judge: JudgeCompleter) -> JudgeConfig:
    """Build the frozen JudgeConfig bound to the actual judge backend."""
    return JudgeConfig(
        judge_provider=judge.provider,
        judge_model_requested=judge.model,
        temperature=0,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        judge_prompt_sha256=compute_judge_prompt_sha256(),
        structured_output_enabled=judge.structured_output_enabled,
        retry_enabled=False,
        self_repair_enabled=False,
    )


@dataclass(frozen=True)
class DiagnosticRunResult:
    """The result of one diagnostic batch run."""

    run_id: str
    dataset_path: str
    repeats: int
    started_at: str
    judge_provider: str
    judge_model_requested: str
    judge_prompt_version: str
    evaluator_version: str
    records: tuple[EvaluationRecord, ...] = ()
    dry_run: bool = False
    validator: dict[str, Any] = field(default_factory=dict)


def _serialize_plan(plan: dict) -> str:
    """Serialize a plan dict to the raw response text the Evaluator consumes."""
    return json.dumps(plan, ensure_ascii=False)


def _evaluate_once(
    pair: dict,
    side: str,
    plan: dict,
    repeat_index: int,
    judge: JudgeCompleter,
    judge_config: JudgeConfig,
) -> EvaluationRecord:
    """Evaluate one plan once and reduce to an :class:`EvaluationRecord`."""
    run_context = build_run_context(pair["pair_id"])
    raw = _serialize_plan(plan)
    result = evaluate_speech_plan(
        pair["input"], raw, run_context, judge_config, judge
    )

    if result.artifact is not None and result.artifact.structural_valid:
        scores = {
            dim: result.artifact.scores[dim].score for dim in DIMENSION_IDS
        }
        flags = tuple(cf.flag for cf in result.artifact.critical_flags)
        return EvaluationRecord(
            pair_id=pair["pair_id"], side=side, repeat_index=repeat_index,
            scores=scores, critical_flags=flags, failure_type=None,
        )

    if result.artifact is not None and not result.artifact.structural_valid:
        # Layer-0 gate failure (should not happen for a curated dataset).
        stage = result.artifact.gate_failure.stage
        return EvaluationRecord(
            pair_id=pair["pair_id"], side=side, repeat_index=repeat_index,
            scores=None, critical_flags=(),
            failure_type=f"gate_{stage}",
        )

    # Evaluator failure artifact.
    failure_type = result.failure.failure_type if result.failure is not None else "unknown"
    return EvaluationRecord(
        pair_id=pair["pair_id"], side=side, repeat_index=repeat_index,
        scores=None, critical_flags=(),
        failure_type=failure_type,
    )


def run_diagnostic(
    dataset_path: Path,
    judge: JudgeCompleter,
    *,
    repeats: int = 3,
) -> DiagnosticRunResult:
    """Run the diagnostic dataset through the Evaluator with *judge*.

    Evaluates each pair's reference and degraded plan ``repeats`` times,
    sequentially and independently, under the frozen condition.
    """
    if repeats < 1:
        raise ValueError(f"repeats must be >= 1, got {repeats}")

    pairs = load_diagnostic_pairs(dataset_path)
    validation = validate_diagnostic_dataset(dataset_path)
    if not validation.all_passed:
        raise ValueError(
            "dataset failed structural validation; aborting before any judge call"
        )

    judge_config = build_judge_config(judge)
    records: list[EvaluationRecord] = []

    for pair in pairs:
        for side, plan in (("reference", pair["reference_plan"]),
                           ("degraded", pair["degraded_plan"])):
            for repeat_index in range(repeats):
                records.append(
                    _evaluate_once(pair, side, plan, repeat_index, judge, judge_config)
                )

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DiagnosticRunResult(
        run_id=run_id,
        dataset_path=str(dataset_path),
        repeats=repeats,
        started_at=_canonical_utc_now(),
        judge_provider=judge_config.judge_provider,
        judge_model_requested=judge_config.judge_model_requested,
        judge_prompt_version=judge_config.judge_prompt_version,
        evaluator_version=EVALUATOR_VERSION,
        records=tuple(records),
        dry_run=False,
        validator=_validator_summary(validation),
    )


def run_diagnostic_dry(dataset_path: Path, *, repeats: int = 3) -> DiagnosticRunResult:
    """Validate the dataset and return an empty run manifest (no judge call)."""
    if repeats < 1:
        raise ValueError(f"repeats must be >= 1, got {repeats}")
    pairs = load_diagnostic_pairs(dataset_path)
    validation = validate_diagnostic_dataset(dataset_path)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DiagnosticRunResult(
        run_id=run_id,
        dataset_path=str(dataset_path),
        repeats=repeats,
        started_at=_canonical_utc_now(),
        judge_provider="",
        judge_model_requested="",
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        records=(),
        dry_run=True,
        validator=_validator_summary(validation),
    )


def _validator_summary(validation) -> dict[str, Any]:
    return {
        "all_passed": validation.all_passed,
        "parsed_count": validation.parsed_count,
        "input_pass_count": validation.input_pass_count,
        "reference_pass_count": validation.reference_pass_count,
        "degraded_pass_count": validation.degraded_pass_count,
        "dataset_checks": validation.dataset_checks,
        "case_error_count": len(validation.case_errors),
    }
