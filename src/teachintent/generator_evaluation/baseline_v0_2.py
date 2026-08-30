"""Generator v0.1 Baseline Evaluation — Protocol **v0.2** (operational revision).

Implements ``docs/generator_v0.1_evaluation_protocol_v0.2.md``
(Status: **Frozen**, frozen 2026-08-30).

``protocol_document_sha256`` is recomputed from the protocol document on every
run, so a run can never be attributed to the void Draft-revision SHA.

What v0.2 changes — and only this
---------------------------------

v0.2 is an **operational revision** of v0.1. It introduces a strict separation
between a **semantic repeat** (the unit of measurement, frozen at 3 per case)
and a **physical attempt** (one invocation of the frozen Evaluator, at most 3
per semantic repeat).

A physical attempt may be repeated **only** when it failed to form a legal
Evaluator artifact. The moment a legal artifact exists, the semantic repeat is
closed — no matter how low the scores are and no matter how many critical flags
were raised. Retry is a function of *artifact legality*, never of *quality*.

What v0.2 does NOT change
-------------------------

* the 30-case canonical population and its fingerprint;
* Evaluator v0.1 and its call contract (``evaluator_retry_enabled`` stays
  ``False`` — the retry added here lives in the runner, not in the Evaluator);
* the Judge condition and Judge Prompt;
* case eligibility (``>= 2`` successful **semantic** repeats);
* every aggregation formula from v0.1;
* critical-flag rules;
* the absence of a Generator PASS/FAIL verdict.

All v0.1 semantic metric functions are **imported and reused**, not copied, so
v0.2 cannot silently drift from the v0.1 mathematics.

Every physical attempt is persisted. A later success never overwrites an
earlier failure.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from ..evaluator import (
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    EvaluationRunContext,
    JudgeCompleter,
    JudgeConfig,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
)
from ..evaluator.errors import (
    EVIDENCE_GROUNDING_ERROR,
    EVIDENCE_SOURCE_ERROR,
    INTERNAL_EVALUATOR_ERROR,
    JUDGE_API_ERROR,
    JUDGE_OUTPUT_SCHEMA_ERROR,
    JUDGE_RESPONSE_PARSE_ERROR,
    SETUP_INPUT_JSONSCHEMA_ERROR,
    SETUP_INPUT_PYDANTIC_ERROR,
    SETUP_JUDGE_CONFIG_ERROR,
    SETUP_RUN_CONTEXT_ERROR,
)
from .baseline_v0_1 import (
    CANONICAL_RUNS,
    CASE_COUNT,
    DIMENSION_LABELS,
    EXPECTED_CALLS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    FROZEN_RETRY_ENABLED,
    FROZEN_SELF_REPAIR_ENABLED,
    FROZEN_STRUCTURED_OUTPUT_ENABLED,
    FROZEN_TEMPERATURE,
    GENERATOR_VERSION,
    GENERATOR_VERSION_PROVENANCE,
    MIN_SUCCESSFUL_REPEATS,
    PROMPT_VERSION,
    PROMPT_VERSION_PROVENANCE,
    REPEATS,
    SEVERE_WEAKNESS_THRESHOLD,
    SOURCE_POPULATION_SHA256,
    WEAKNESS_THRESHOLD,
    BaselineRecord,
    BaselineRun,
    CanonicalCase,
    CanonicalRunSpec,
    _canonical_utc_now,
    _sha256_file,
    _utc_run_id,
    _write_group_metrics_csv,
    _write_json,
    block_metrics,
    build_baseline_judge,
    build_frozen_judge_config,
    case_diagnostics,
    global_metrics,
    intent_metrics,
    plan_baseline_calls,
    prepare_baseline_run,
    reduce_result,
)

__all__ = [
    # ---- Protocol identity ----
    "PROTOCOL_VERSION",
    "PROTOCOL_STATUS",
    "PROTOCOL_DOC_PATH",
    "PROTOCOL_V0_1_DOC_PATH",
    # ---- Frozen inherited constants (re-exported) ----
    "SOURCE_POPULATION_SHA256",
    "CASE_COUNT",
    "CANONICAL_RUNS",
    "REPEATS",
    "MIN_SUCCESSFUL_REPEATS",
    "PLANNED_SEMANTIC_REPEATS",
    "EXPECTED_CALLS",
    "GENERATOR_VERSION",
    "GENERATOR_VERSION_PROVENANCE",
    "PROMPT_VERSION",
    "PROMPT_VERSION_PROVENANCE",
    # ---- Attempt policy ----
    "MAX_ATTEMPTS_PER_SEMANTIC_REPEAT",
    "MAX_POSSIBLE_PHYSICAL_ATTEMPTS",
    "BASELINE_ATTEMPT_RETRY_ENABLED",
    "EVALUATOR_RETRY_ENABLED",
    "RETRYABLE_FAILURE_TYPES",
    "NON_RETRYABLE_FAILURE_TYPES",
    "RETRY_BACKOFF_SECONDS",
    "STOPPED_VALID_ARTIFACT",
    "STOPPED_EXHAUSTED",
    "STOPPED_NON_RETRYABLE",
    "GATE_FAILURE_PREFIX",
    # ---- Data types ----
    "AttemptRecord",
    "SemanticRepeatResult",
    "BaselineRunV2",
    # ---- Policy helpers ----
    "is_retryable_failure",
    "backoff_seconds",
    "attempt_failure_type",
    "attempt_summary",
    # ---- Planning / preparation ----
    "plan_semantic_repeats",
    "prepare_baseline_run_v2",
    "build_baseline_judge",
    "build_frozen_judge_config",
    # ---- Execution ----
    "evaluate_attempt",
    "build_attempt_record",
    "execute_semantic_repeat",
    "execute_baseline_run_v2",
    # ---- Metrics ----
    "attempt_failure_taxonomy_counts",
    "operational_attempt_metrics",
    "case_attempt_diagnostics",
    "case_diagnostics_v0_2",
    "global_metrics_v0_2",
    "aggregate_v0_2",
    # ---- Artifacts ----
    "build_manifest_v2",
    "build_summary_v2",
    "write_artifacts_v2",
]

# ---------------------------------------------------------------------------
# Protocol identity.
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "v0.2"
#: Frozen 2026-08-30 after human QC. Protocol v0.2 is no longer a Draft.
PROTOCOL_STATUS = "Frozen"
PROTOCOL_DOC_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "generator_v0.1_evaluation_protocol_v0.2.md"
)
#: The v0.1 document stays Frozen and unmodified; recorded for provenance only.
PROTOCOL_V0_1_DOC_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "generator_v0.1_evaluation_protocol_v0.1.md"
)

# ---------------------------------------------------------------------------
# Design constants (Section 5).
# ---------------------------------------------------------------------------
PLANNED_SEMANTIC_REPEATS = CASE_COUNT * REPEATS  # 90
MAX_ATTEMPTS_PER_SEMANTIC_REPEAT = 3
MAX_POSSIBLE_PHYSICAL_ATTEMPTS = (
    PLANNED_SEMANTIC_REPEATS * MAX_ATTEMPTS_PER_SEMANTIC_REPEAT
)  # 270

# ---------------------------------------------------------------------------
# Retry policy (Sections 4.1, 6, 8).
#
# Two DIFFERENT retry concepts. They are never conflated:
#   * EVALUATOR_RETRY_ENABLED      -> Evaluator v0.1 internal retry (frozen False)
#   * BASELINE_ATTEMPT_RETRY_ENABLED -> this runner's outer attempt policy (True)
# ---------------------------------------------------------------------------
EVALUATOR_RETRY_ENABLED = FROZEN_RETRY_ENABLED  # False — Evaluator v0.1 internal
BASELINE_ATTEMPT_RETRY_ENABLED = True

#: Retryable iff the attempt failed to form a legal Evaluator artifact AND the
#: failure type is one of these (Protocol v0.2 Section 6.1).
RETRYABLE_FAILURE_TYPES: tuple[str, ...] = (
    JUDGE_API_ERROR,
    JUDGE_RESPONSE_PARSE_ERROR,
    JUDGE_OUTPUT_SCHEMA_ERROR,
    EVIDENCE_SOURCE_ERROR,
    EVIDENCE_GROUNDING_ERROR,
)

#: Non-retryable / fatal (Protocol v0.2 Section 6.2).
NON_RETRYABLE_FAILURE_TYPES: tuple[str, ...] = (
    SETUP_INPUT_JSONSCHEMA_ERROR,
    SETUP_INPUT_PYDANTIC_ERROR,
    SETUP_RUN_CONTEXT_ERROR,
    SETUP_JUDGE_CONFIG_ERROR,
    INTERNAL_EVALUATOR_ERROR,
)

#: Layer-0 structural failure of a canonical Generator output. Deterministic
#: given the (frozen) raw response, so retrying the Judge can never change it.
#: Treated as an invariant violation and never masked by a retry (Section 6.3).
GATE_FAILURE_PREFIX = "gate_"

#: Backoff before the NEXT attempt, indexed by the 1-based index of the failed
#: attempt: index 0 -> before attempt 2, index 1 -> before attempt 3.
RETRY_BACKOFF_SECONDS: dict[str, tuple[float, ...]] = {
    JUDGE_API_ERROR: (5.0, 15.0),
    "DEFAULT": (2.0, 2.0),
}

STOPPED_VALID_ARTIFACT = "valid_artifact"
STOPPED_EXHAUSTED = "exhausted_max_attempts"
STOPPED_NON_RETRYABLE = "non_retryable_failure"


# ---------------------------------------------------------------------------
# Data types.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AttemptRecord:
    """One **physical attempt** — one invocation of the frozen Evaluator.

    Every attempt is persisted, including every failed attempt that was later
    recovered by a retry. ``artifact`` is the verbatim Evaluator artifact dump
    (``None`` when no legal artifact was formed).
    """

    case_id: str
    block: str
    intent: str
    repeat_index: int
    attempt_index: int
    started_at: str
    completed_at: str
    outcome: str  # "artifact" | "failure"
    failure_type: str | None
    failure_summary: str | None
    artifact: dict | None
    judge_model_reported: str | None
    run_metadata: dict | None
    retryable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "block": self.block,
            "intent": self.intent,
            "repeat_index": self.repeat_index,
            "attempt_index": self.attempt_index,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
            "failure_type": self.failure_type,
            "failure_summary": self.failure_summary,
            "artifact": self.artifact,
            "judge_model_reported": self.judge_model_reported,
            "run_metadata": self.run_metadata,
            "retryable": self.retryable,
        }


@dataclass
class SemanticRepeatResult:
    """The outcome of **one semantic repeat** (possibly several attempts)."""

    case_id: str
    block: str
    intent: str
    repeat_index: int
    semantic_repeat_success: bool
    successful_attempt_index: int | None
    attempt_count: int
    attempt_failure_types: tuple[str, ...]
    final_artifact: dict | None
    stopped_reason: str
    attempts: tuple[AttemptRecord, ...] = ()
    #: The defining :class:`EvaluatorResult` (successful attempt, or the last
    #: attempt when the repeat failed). NOT serialized — it is the source from
    #: which the :class:`BaselineRecord` is derived via v0.1 ``reduce_result``.
    final_result: Any = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready record for ``evaluations.jsonl`` (every attempt kept)."""
        return {
            "case_id": self.case_id,
            "block": self.block,
            "intent": self.intent,
            "repeat_index": self.repeat_index,
            "semantic_repeat_success": self.semantic_repeat_success,
            "successful_attempt_index": self.successful_attempt_index,
            "attempt_count": self.attempt_count,
            "attempt_failure_types": list(self.attempt_failure_types),
            "final_artifact": self.final_artifact,
            "stopped_reason": self.stopped_reason,
            "attempts": [a.to_dict() for a in self.attempts],
        }


@dataclass
class BaselineRunV2:
    """State for one Protocol v0.2 baseline evaluation run."""

    run_id: str
    started_at: str
    completed_at: str | None = None
    dry_run: bool = True
    protocol_version: str = PROTOCOL_VERSION
    protocol_status: str = PROTOCOL_STATUS
    protocol_document_sha256: str = ""
    source_runs: list[dict] = field(default_factory=list)
    integrity: Any = None
    cases: list[CanonicalCase] = field(default_factory=list)
    semantic_repeats_per_case: int = REPEATS
    planned_semantic_repeats: int = PLANNED_SEMANTIC_REPEATS
    max_attempts_per_semantic_repeat: int = MAX_ATTEMPTS_PER_SEMANTIC_REPEAT
    max_possible_physical_attempts: int = MAX_POSSIBLE_PHYSICAL_ATTEMPTS
    generator_version: str = GENERATOR_VERSION
    generator_version_provenance: str = GENERATOR_VERSION_PROVENANCE
    prompt_version: str = PROMPT_VERSION
    prompt_version_provenance: str = PROMPT_VERSION_PROVENANCE
    source_population_sha256: str = ""
    source_population_sha256_expected: str = SOURCE_POPULATION_SHA256
    source_population_sha256_match: bool = False
    judge_provider: str | None = None
    judge_model_requested: str | None = None
    judge_model_reported: tuple[str, ...] = ()
    #: Exactly one record per semantic repeat (90). Aggregation input.
    records: tuple[BaselineRecord, ...] = ()
    #: Exactly one result per semantic repeat (90), carrying every attempt.
    repeat_results: tuple[SemanticRepeatResult, ...] = ()
    #: JSONL records (one per semantic repeat, attempts nested).
    raw_evaluations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy helpers (pure).
# ---------------------------------------------------------------------------
def attempt_failure_type(result) -> str | None:
    """Frozen failure type of one EvaluatorResult (``None`` on legal artifact).

    A Layer-0 structural failure is reported as ``gate_<stage>`` and is NEVER
    retryable (Protocol v0.2 Section 6.3).
    """
    artifact = result.artifact
    if artifact is not None and artifact.structural_valid:
        return None
    if artifact is not None and not artifact.structural_valid:
        return f"{GATE_FAILURE_PREFIX}{artifact.gate_failure.stage}"
    if result.failure is not None:
        return result.failure.failure_type
    return "unknown"


def attempt_summary(result) -> str | None:
    """Human-readable failure summary for one EvaluatorResult (no secrets)."""
    artifact = result.artifact
    if artifact is not None and artifact.structural_valid:
        return None
    if artifact is not None and not artifact.structural_valid:
        return artifact.gate_failure.summary
    if result.failure is not None:
        return result.failure.summary
    return None


def is_retryable_failure(failure_type: str | None) -> bool:
    """True iff this failure permits another physical attempt.

    The decision depends **only** on the failure type. Scores, critical flags,
    intent, block and human opinion are not inputs (Section 6.4).
    """
    return failure_type in RETRYABLE_FAILURE_TYPES


def backoff_seconds(failure_type: str | None, failed_attempt_index: int) -> float:
    """Seconds to sleep before attempt ``failed_attempt_index + 1``.

    ``judge_api_error`` uses 5 s then 15 s; every other retryable failure uses a
    fixed 2 s (Protocol v0.2 Section 8).
    """
    schedule = RETRY_BACKOFF_SECONDS.get(
        failure_type or "", RETRY_BACKOFF_SECONDS["DEFAULT"]
    )
    position = failed_attempt_index - 1
    if position < 0 or position >= len(schedule):
        return 0.0
    return schedule[position]


# ---------------------------------------------------------------------------
# Planning / preparation (offline; no API).
# ---------------------------------------------------------------------------
def plan_semantic_repeats(
    cases: Sequence[CanonicalCase],
    repeats: int = REPEATS,
) -> list[dict]:
    """The semantic plan (identical to v0.1): 30 cases x 3 repeats = 90.

    Physical attempts are NOT part of the plan: 270 is an upper bound on Judge
    calls, never the size of the experiment (Section 5.4).
    """
    return plan_baseline_calls(cases, repeats)


def prepare_baseline_run_v2(
    runs: Sequence[CanonicalRunSpec] = CANONICAL_RUNS,
    *,
    repeats: int = REPEATS,
) -> BaselineRunV2:
    """Load + verify the canonical population and plan the 90 semantic repeats.

    Reuses the frozen v0.1 pre-flight (population integrity + fingerprint)
    verbatim; only the protocol identity fields are overridden. Never calls the
    Judge.
    """
    if repeats != REPEATS:
        raise ValueError(
            f"repeats must be exactly {REPEATS}: the baseline design is fixed at "
            f"{CASE_COUNT} cases x {REPEATS} semantic repeats = "
            f"{PLANNED_SEMANTIC_REPEATS} planned semantic repeats "
            f"(got {repeats})"
        )

    v1_run: BaselineRun = prepare_baseline_run(runs, repeats=repeats)
    doc = PROTOCOL_DOC_PATH
    return BaselineRunV2(
        run_id=_utc_run_id(),
        started_at=_canonical_utc_now(),
        dry_run=True,
        protocol_version=PROTOCOL_VERSION,
        protocol_status=PROTOCOL_STATUS,
        protocol_document_sha256=_sha256_file(doc) if doc.is_file() else "",
        source_runs=list(v1_run.source_runs),
        integrity=v1_run.integrity,
        cases=list(v1_run.cases),
        semantic_repeats_per_case=v1_run.repeats,
        planned_semantic_repeats=len(v1_run.cases) * v1_run.repeats,
        generator_version=v1_run.generator_version,
        generator_version_provenance=v1_run.generator_version_provenance,
        prompt_version=v1_run.prompt_version,
        prompt_version_provenance=v1_run.prompt_version_provenance,
        source_population_sha256=v1_run.source_population_sha256,
        source_population_sha256_expected=v1_run.source_population_sha256_expected,
        source_population_sha256_match=v1_run.source_population_sha256_match,
    )


# ---------------------------------------------------------------------------
# Execution (real mode only; never called in dry-run).
# ---------------------------------------------------------------------------
def evaluate_attempt(
    case: CanonicalCase,
    repeat_index: int,
    attempt_index: int,
    judge: JudgeCompleter,
    judge_config: JudgeConfig,
):
    """Run ONE physical attempt through the frozen Evaluator.

    ``Evaluator v0.1`` is called exactly once (``evaluator_retry_enabled =
    False``). The attempt index is visible only in ``input_case_id``; it never
    reaches the Judge payload.
    """
    eval_id = f"{case.case_id}__r{repeat_index}__a{attempt_index}"
    ctx = EvaluationRunContext(
        input_case_id=eval_id,
        generator_version=case.generator_version,
        prompt_version=case.prompt_version,
    )
    return evaluate_speech_plan(
        case.input_doc, case.raw_response, ctx, judge_config, judge
    )


def build_attempt_record(
    case: CanonicalCase,
    repeat_index: int,
    attempt_index: int,
    result,
    started_at: str,
    completed_at: str,
) -> AttemptRecord:
    """Reduce one EvaluatorResult to a persistable :class:`AttemptRecord`."""
    failure_type = attempt_failure_type(result)
    artifact_dump: dict | None = None
    metadata_dump: dict | None = None
    reported: str | None = None

    if result.artifact is not None:
        artifact_dump = result.artifact.model_dump(mode="json")
        metadata_dump = artifact_dump.get("run_metadata")
        reported = (metadata_dump or {}).get("judge_model_reported")
    elif result.failure is not None:
        failure_dump = result.failure.model_dump(mode="json")
        metadata_dump = failure_dump.get("run_metadata")
        reported = (metadata_dump or {}).get("judge_model_reported")

    if result.artifact is not None and result.artifact.structural_valid:
        outcome = "artifact"
    elif result.artifact is not None or result.failure is not None:
        outcome = "failure"
    else:  # pragma: no cover — defensive
        outcome = "unknown"

    return AttemptRecord(
        case_id=case.case_id,
        block=case.block,
        intent=case.intent,
        repeat_index=repeat_index,
        attempt_index=attempt_index,
        started_at=started_at,
        completed_at=completed_at,
        outcome=outcome,
        failure_type=failure_type,
        failure_summary=attempt_summary(result),
        artifact=artifact_dump if outcome == "artifact" else None,
        judge_model_reported=reported,
        run_metadata=metadata_dump,
        retryable=is_retryable_failure(failure_type),
    )


def execute_semantic_repeat(
    case: CanonicalCase,
    repeat_index: int,
    judge: JudgeCompleter,
    judge_config: JudgeConfig,
    *,
    max_attempts: int = MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> SemanticRepeatResult:
    """Acquire ONE legal Evaluator artifact for one semantic repeat.

    Retry rules (Protocol v0.2 Section 7):

    * attempt 1 produces a legal artifact -> STOP immediately (Case A);
    * retryable failure and attempts remain -> sleep the frozen backoff, then
      attempt again (Case B);
    * all ``max_attempts`` attempts fail retryably -> the semantic repeat fails
      and every attempt is recorded (Case C); attempt ``max_attempts + 1`` is
      never made;
    * non-retryable failure -> STOP immediately (Case D).

    ``sleep_fn`` is injectable so tests never wait in real time.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    attempts: list[AttemptRecord] = []
    failure_types: list[str] = []
    stopped_reason = STOPPED_EXHAUSTED
    success_index: int | None = None
    final_result = None

    for attempt_index in range(1, max_attempts + 1):
        started_at = _canonical_utc_now()
        result = evaluate_attempt(
            case, repeat_index, attempt_index, judge, judge_config
        )
        completed_at = _canonical_utc_now()

        record = build_attempt_record(
            case, repeat_index, attempt_index, result, started_at, completed_at
        )
        attempts.append(record)
        final_result = result

        if record.failure_type is None:
            # ---- Case A: a legal artifact exists. STOP. Unconditionally. ----
            success_index = attempt_index
            stopped_reason = STOPPED_VALID_ARTIFACT
            break

        failure_types.append(record.failure_type)

        if not record.retryable:
            # ---- Case D: non-retryable / invariant violation. STOP. ----
            stopped_reason = STOPPED_NON_RETRYABLE
            break

        if attempt_index < max_attempts:
            # ---- Case B: retryable and attempts remain -> backoff, retry. ----
            delay = backoff_seconds(record.failure_type, attempt_index)
            if delay:
                sleep_fn(delay)
    # ---- Case C falls through: loop exhausted with no legal artifact. ----

    artifact_dump = attempts[-1].artifact if success_index is not None else None
    return SemanticRepeatResult(
        case_id=case.case_id,
        block=case.block,
        intent=case.intent,
        repeat_index=repeat_index,
        semantic_repeat_success=success_index is not None,
        successful_attempt_index=success_index,
        attempt_count=len(attempts),
        attempt_failure_types=tuple(failure_types),
        final_artifact=artifact_dump,
        stopped_reason=stopped_reason,
        attempts=tuple(attempts),
        final_result=final_result,
    )


def execute_baseline_run_v2(
    run: BaselineRunV2,
    judge: JudgeCompleter,
    *,
    max_attempts: int = MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Execute the v0.2 baseline run. Fills ``run`` in place.

    Exactly ``len(run.cases) * run.semantic_repeats_per_case`` semantic repeats
    are executed; each may consume up to ``max_attempts`` physical attempts.
    """
    if max_attempts != MAX_ATTEMPTS_PER_SEMANTIC_REPEAT:
        raise ValueError(
            f"max_attempts must be exactly {MAX_ATTEMPTS_PER_SEMANTIC_REPEAT} "
            f"(Protocol v0.2 Section 7); got {max_attempts}"
        )

    judge_config = build_frozen_judge_config(judge)

    run.dry_run = False
    run.judge_provider = judge.provider
    run.judge_model_requested = judge.model
    run.max_attempts_per_semantic_repeat = max_attempts

    repeat_results: list[SemanticRepeatResult] = []
    records: list[BaselineRecord] = []
    raw_evaluations: list[dict] = []
    reported: set[str] = set()

    for case in run.cases:
        for repeat_index in range(1, run.semantic_repeats_per_case + 1):
            outcome = execute_semantic_repeat(
                case,
                repeat_index,
                judge,
                judge_config,
                max_attempts=max_attempts,
                sleep_fn=sleep_fn,
            )
            repeat_results.append(outcome)
            # The semantic record is derived by the FROZEN v0.1 reducer, so the
            # aggregation mathematics is literally the v0.1 code path.
            records.append(reduce_result(case, repeat_index, outcome.final_result))
            raw_evaluations.append(outcome.to_dict())
            for attempt in outcome.attempts:
                if attempt.judge_model_reported:
                    reported.add(attempt.judge_model_reported)

    run.repeat_results = tuple(repeat_results)
    run.records = tuple(records)
    run.raw_evaluations = raw_evaluations
    run.judge_model_reported = tuple(sorted(reported))
    run.completed_at = _canonical_utc_now()


# ---------------------------------------------------------------------------
# Operational attempt metrics (Section 14.2).
# ---------------------------------------------------------------------------
def attempt_failure_taxonomy_counts(
    repeat_results: Iterable[SemanticRepeatResult],
) -> dict[str, int]:
    """Counts over **every failed attempt** (up to 2 per semantic repeat).

    Distinct from the v0.1 ``failure_taxonomy_counts``, which counts one failure
    type per failed **semantic repeat**. Both are reported; they are not
    interchangeable.
    """
    counts: dict[str, int] = {}
    for outcome in repeat_results:
        for failure_type in outcome.attempt_failure_types:
            counts[failure_type] = counts.get(failure_type, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def _ratio(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def operational_attempt_metrics(
    repeat_results: Sequence[SemanticRepeatResult],
    *,
    planned: int = PLANNED_SEMANTIC_REPEATS,
    max_possible_physical_attempts: int = MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
) -> dict[str, Any]:
    """Operational attempt statistics (Protocol v0.2 Section 14.2)."""
    results = list(repeat_results)

    successful = sum(1 for r in results if r.semantic_repeat_success)
    failed = sum(1 for r in results if not r.semantic_repeat_success)
    total_attempts = sum(r.attempt_count for r in results)
    first_attempt_successes = sum(
        1 for r in results if r.successful_attempt_index == 1
    )
    recovered = sum(
        1
        for r in results
        if r.semantic_repeat_success and (r.successful_attempt_index or 0) > 1
    )
    exhausted = sum(
        1 for r in results if r.stopped_reason == STOPPED_EXHAUSTED
    )
    # Denominator of retry_recovery_rate, defined exactly (Section 14.2):
    # semantic repeats whose ATTEMPT 1 failed with a retryable failure type.
    retryable_first_attempt_failures = sum(
        1
        for r in results
        if r.attempts
        and r.attempts[0].failure_type is not None
        and r.attempts[0].retryable
    )

    return {
        "planned_semantic_repeats": planned,
        "successful_semantic_repeats": successful,
        "failed_semantic_repeats": failed,
        "semantic_repeat_success_rate": _ratio(successful, planned),
        "total_physical_attempts": total_attempts,
        "successful_first_attempts": first_attempt_successes,
        "successful_after_retry": recovered,
        "exhausted_after_max_attempts": exhausted,
        "retryable_first_attempt_failures": retryable_first_attempt_failures,
        "non_retryable_terminations": sum(
            1 for r in results if r.stopped_reason == STOPPED_NON_RETRYABLE
        ),
        "mean_attempts_per_semantic_repeat": _ratio(total_attempts, planned),
        "attempt_failure_taxonomy_counts": attempt_failure_taxonomy_counts(results),
        "first_attempt_success_rate": _ratio(first_attempt_successes, planned),
        "retry_recovery_rate": _ratio(recovered, retryable_first_attempt_failures),
        "max_possible_physical_attempts": max_possible_physical_attempts,
        "actual_physical_attempts": total_attempts,
    }


# ---------------------------------------------------------------------------
# Per-case retry diagnostics (Section 14.3).
# ---------------------------------------------------------------------------
def case_attempt_diagnostics(
    repeat_results: Sequence[SemanticRepeatResult],
    case_id: str,
) -> dict[str, Any]:
    """Operational retry statistics for one case."""
    rows = [r for r in repeat_results if r.case_id == case_id]
    failure_types: list[str] = []
    for row in sorted(rows, key=lambda r: r.repeat_index):
        failure_types.extend(row.attempt_failure_types)
    return {
        "successful_semantic_repeats": sum(
            1 for r in rows if r.semantic_repeat_success
        ),
        "failed_semantic_repeats": sum(
            1 for r in rows if not r.semantic_repeat_success
        ),
        "total_physical_attempts": sum(r.attempt_count for r in rows),
        "first_attempt_successes": sum(
            1 for r in rows if r.successful_attempt_index == 1
        ),
        "recovered_by_retry_count": sum(
            1
            for r in rows
            if r.semantic_repeat_success and (r.successful_attempt_index or 0) > 1
        ),
        "exhausted_repeat_count": sum(
            1 for r in rows if r.stopped_reason == STOPPED_EXHAUSTED
        ),
        "attempt_failure_types": sorted(set(failure_types)),
    }


def case_diagnostics_v0_2(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
    repeat_results: Sequence[SemanticRepeatResult],
) -> list[dict[str, Any]]:
    """v0.1 per-case diagnostics **plus** the v0.2 retry information."""
    rows = case_diagnostics(records, cases)
    for row in rows:
        row.update(case_attempt_diagnostics(repeat_results, row["case_id"]))
    return rows


def global_metrics_v0_2(
    records: Sequence[BaselineRecord],
    cases: Sequence[CanonicalCase],
    repeat_results: Sequence[SemanticRepeatResult],
) -> dict[str, Any]:
    """v0.1 global semantic metrics **plus** the operational attempt block."""
    metrics = global_metrics(records, cases)
    metrics["operational_attempt_metrics"] = operational_attempt_metrics(
        repeat_results
    )
    return metrics


def aggregate_v0_2(run: BaselineRunV2) -> dict[str, Any]:
    """All v0.2 metrics. Semantic aggregation reuses the v0.1 code path."""
    return {
        "global": global_metrics_v0_2(run.records, run.cases, run.repeat_results),
        "intent": intent_metrics(run.records, run.cases),
        "block": block_metrics(run.records, run.cases),
        "cases": case_diagnostics_v0_2(run.records, run.cases, run.repeat_results),
    }


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------
def _attempt_policy_block() -> dict[str, Any]:
    return {
        "evaluator_retry_enabled": EVALUATOR_RETRY_ENABLED,
        "baseline_attempt_retry_enabled": BASELINE_ATTEMPT_RETRY_ENABLED,
        "max_attempts_per_semantic_repeat": MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
        "retryable_failure_types": list(RETRYABLE_FAILURE_TYPES),
        "non_retryable_failure_types": list(NON_RETRYABLE_FAILURE_TYPES),
        "retry_backoff_policy": {
            failure_type: list(values)
            for failure_type, values in RETRY_BACKOFF_SECONDS.items()
        },
        "retry_backoff_policy_note": (
            "Values are seconds to sleep BEFORE the next attempt, indexed by "
            "the 1-based index of the failed attempt: [before attempt 2, "
            "before attempt 3]."
        ),
    }


def build_manifest_v2(run: BaselineRunV2) -> dict[str, Any]:
    """Run manifest (Protocol v0.2 Section 17). No secrets."""
    integrity = run.integrity
    return {
        "run_id": run.run_id,
        "protocol_version": run.protocol_version,
        "protocol_status": run.protocol_status,
        "protocol_document_path": str(PROTOCOL_DOC_PATH),
        "protocol_document_sha256": run.protocol_document_sha256,
        "protocol_v0_1_document_path": str(PROTOCOL_V0_1_DOC_PATH),
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        # ---- Source: three canonical Generator v0.1 Pilot runs (reused) ----
        "source_runs": run.source_runs,
        "source_run_ids": [s["run_id"] for s in run.source_runs],
        "source_run_paths": [s["path"] for s in run.source_runs],
        # ---- Population fingerprint (inherited, unchanged) ----
        "source_population_sha256": run.source_population_sha256,
        "source_population_sha256_expected": run.source_population_sha256_expected,
        "source_population_sha256_match": run.source_population_sha256_match,
        "source_population_records": (
            integrity.population_records if integrity is not None else []
        ),
        # ---- Frozen Generator side ----
        "generator_version": run.generator_version,
        "generator_version_provenance": run.generator_version_provenance,
        "prompt_version": run.prompt_version,
        "prompt_version_provenance": run.prompt_version_provenance,
        "case_count": len(run.cases),
        "case_ids": [c.case_id for c in run.cases],
        "per_block_case_counts": (
            integrity.per_block_counts if integrity is not None else {}
        ),
        "unique_case_ids": integrity.unique_case_ids if integrity is not None else None,
        "population_integrity_ok": integrity.ok if integrity is not None else None,
        # ---- Frozen Evaluator side ----
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": run.judge_provider or FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": (
            run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED
        ),
        "judge_model_reported": list(run.judge_model_reported),
        "temperature": FROZEN_TEMPERATURE,
        "structured_output_enabled": FROZEN_STRUCTURED_OUTPUT_ENABLED,
        "self_repair_enabled": FROZEN_SELF_REPAIR_ENABLED,
        # ---- Evaluator-internal retry vs runner attempt retry ----
        "evaluator_retry_enabled": EVALUATOR_RETRY_ENABLED,
        **_attempt_policy_block(),
        # ---- Design (semantic repeats vs physical attempts) ----
        "case_count_design": CASE_COUNT,
        "semantic_repeats_per_case": run.semantic_repeats_per_case,
        "planned_semantic_repeats": run.planned_semantic_repeats,
        "max_possible_physical_attempts": run.max_possible_physical_attempts,
        "actual_physical_attempts": sum(
            r.attempt_count for r in run.repeat_results
        ),
        "planned_calls": run.planned_semantic_repeats,
        "successful_evaluations": sum(1 for r in run.records if r.scores is not None),
        "failed_evaluations": sum(1 for r in run.records if r.scores is None),
    }


def build_summary_v2(
    run: BaselineRunV2, agg: dict[str, Any] | None
) -> dict[str, Any]:
    """summary.json: provenance + semantic metrics + operational metrics."""
    operational = (
        agg["global"]["operational_attempt_metrics"] if agg is not None else None
    )
    summary: dict[str, Any] = {
        "run_id": run.run_id,
        "protocol_version": run.protocol_version,
        "protocol_status": run.protocol_status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        "source_run_ids": [s["run_id"] for s in run.source_runs],
        "source_population_sha256": run.source_population_sha256,
        "source_population_sha256_expected": run.source_population_sha256_expected,
        "source_population_sha256_match": run.source_population_sha256_match,
        "generator_version": run.generator_version,
        "generator_version_provenance": run.generator_version_provenance,
        "prompt_version": run.prompt_version,
        "prompt_version_provenance": run.prompt_version_provenance,
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": run.judge_provider or FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": (
            run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED
        ),
        "judge_model_reported": list(run.judge_model_reported),
        "temperature": FROZEN_TEMPERATURE,
        "structured_output_enabled": FROZEN_STRUCTURED_OUTPUT_ENABLED,
        "self_repair_enabled": FROZEN_SELF_REPAIR_ENABLED,
        # ---- Two distinct retry concepts, recorded separately ----
        "evaluator_retry_enabled": EVALUATOR_RETRY_ENABLED,
        **_attempt_policy_block(),
        # ---- Design ----
        "case_count": len(run.cases),
        "semantic_repeats_per_case": run.semantic_repeats_per_case,
        "planned_semantic_repeats": run.planned_semantic_repeats,
        "max_possible_physical_attempts": run.max_possible_physical_attempts,
        "actual_physical_attempts": sum(
            r.attempt_count for r in run.repeat_results
        ),
        # Descriptive baseline — NO acceptance verdict.
        "verdict": None,
        "verdict_note": (
            "Generator v0.1 Baseline Evaluation (descriptive). No Generator "
            "PASS/FAIL threshold is defined by this protocol."
        ),
        "operational_attempt_metrics": operational,
    }
    if agg is not None:
        summary.update(
            {
                "global_metrics": agg["global"],
                "intent_metrics": agg["intent"],
                "block_metrics": agg["block"],
                "case_diagnostics": agg["cases"],
                "diagnostic_thresholds": {
                    "weakness_dimension_mean_lt": WEAKNESS_THRESHOLD,
                    "severe_weakness_dimension_mean_lt": SEVERE_WEAKNESS_THRESHOLD,
                    "note": (
                        "Diagnostic thresholds only. Not a validated "
                        "PASS/FAIL benchmark."
                    ),
                },
            }
        )
    else:
        summary["metrics"] = None
    return summary


_CASE_CSV_HEADER: tuple[str, ...] = (
    ("case_id", "block", "block_name", "intent", "eligible", "exclusion_reason")
    + (
        "successful_repeats",
        "successful_semantic_repeats",
        "failed_semantic_repeats",
        "total_physical_attempts",
        "first_attempt_successes",
        "recovered_by_retry_count",
        "exhausted_repeat_count",
    )
    + tuple(DIMENSION_LABELS)
    + (
        "overall_mean",
        "critical_flags",
        "repeat_level_flags",
        "failure_types",
        "attempt_failure_types",
        "weak_dimensions",
        "severe_dimensions",
    )
)


def _write_case_metrics_csv_v2(
    path: Path, rows: Sequence[dict[str, Any]]
) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(_CASE_CSV_HEADER))
        for row in rows:
            means = row["dimension_means"] or {}
            writer.writerow(
                [
                    row["case_id"],
                    row["block"],
                    row["block_name"],
                    row["intent"],
                    row["eligible"],
                    row["exclusion_reason"] or "",
                    row["successful_repeats"],
                    row["successful_semantic_repeats"],
                    row["failed_semantic_repeats"],
                    row["total_physical_attempts"],
                    row["first_attempt_successes"],
                    row["recovered_by_retry_count"],
                    row["exhausted_repeat_count"],
                ]
                + [means.get(label, "") for label in DIMENSION_LABELS]
                + [
                    "" if row["overall_mean"] is None else row["overall_mean"],
                    "|".join(row["critical_flags"]),
                    "|".join(row["repeat_level_flags"]),
                    "|".join(row["failure_types"]),
                    "|".join(row["attempt_failure_types"]),
                    "|".join(row["weak_dimensions"]),
                    "|".join(row["severe_dimensions"]),
                ]
            )


def write_artifacts_v2(
    run: BaselineRunV2,
    out_dir: Path | str,
    *,
    agg: dict[str, Any] | None = None,
) -> None:
    """Write the v0.2 artifact set. ``agg`` is omitted in dry-run mode."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(out_dir / "run_manifest.json", build_manifest_v2(run))
    _write_json(out_dir / "summary.json", build_summary_v2(run, agg))

    if agg is not None:
        _write_case_metrics_csv_v2(out_dir / "case_metrics.csv", agg["cases"])
        _write_group_metrics_csv(
            out_dir / "intent_metrics.csv", agg["intent"], key_header="intent"
        )
        _write_group_metrics_csv(
            out_dir / "block_metrics.csv",
            agg["block"],
            key_header="block",
            extra_columns=("block_name",),
        )

    if run.raw_evaluations:
        with (out_dir / "evaluations.jsonl").open("w", encoding="utf-8") as handle:
            for rec in run.raw_evaluations:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

    (out_dir / "README.md").write_text(_readme_text_v2(run, agg), encoding="utf-8")


def _readme_text_v2(run: BaselineRunV2, agg: dict[str, Any] | None) -> str:
    lines = [
        "# Generator v0.1 Baseline Evaluation — Protocol v0.2",
        "",
        f"- run_id: {run.run_id}",
        f"- protocol_version: {run.protocol_version} (status: {run.protocol_status})",
        f"- started_at: {run.started_at}",
        f"- completed_at: {run.completed_at}",
        f"- dry_run: {run.dry_run}",
        "",
        "## Source (canonical Generator v0.1 Pilot runs, reused as-is)",
        "",
    ]
    for src in run.source_runs:
        lines.append(
            f"- Block {src['block']} ({src['block_name']}): run `{src['run_id']}` "
            f"— {src['actual_cases']}/{src['expected_cases']} cases"
        )
    lines += [
        f"- total cases: {len(run.cases)}",
        f"- source_population_sha256: {run.source_population_sha256}",
        f"- source_population_sha256_match: {run.source_population_sha256_match}",
        "",
        "## Evaluator",
        "",
        f"- evaluator_version: {EVALUATOR_VERSION}",
        f"- judge_prompt_version: {JUDGE_PROMPT_VERSION}",
        f"- judge_provider: {run.judge_provider or FROZEN_JUDGE_PROVIDER}",
        f"- judge_model_requested: "
        f"{run.judge_model_requested or FROZEN_JUDGE_MODEL_REQUESTED}",
        f"- temperature: {FROZEN_TEMPERATURE}"
        f" / structured_output: {FROZEN_STRUCTURED_OUTPUT_ENABLED}"
        f" / self_repair: {FROZEN_SELF_REPAIR_ENABLED}",
        f"- evaluator internal retry: {EVALUATOR_RETRY_ENABLED} (Evaluator v0.1)",
        f"- baseline attempt retry: {BASELINE_ATTEMPT_RETRY_ENABLED} (runner policy)",
        f"- max attempts per semantic repeat: {run.max_attempts_per_semantic_repeat}",
        "",
        "## Design",
        "",
        f"- semantic repeats per case: {run.semantic_repeats_per_case}",
        f"- planned semantic repeats: {run.planned_semantic_repeats}",
        f"- max possible physical attempts: {run.max_possible_physical_attempts}",
        "",
        "This is a descriptive baseline. No Generator PASS/FAIL threshold is defined.",
        "",
        "Artifacts: run_manifest.json / summary.json / evaluations.jsonl /",
        "case_metrics.csv / intent_metrics.csv / block_metrics.csv.",
        "",
        "`evaluations.jsonl` holds one record per semantic repeat; each record",
        "embeds EVERY physical attempt of that repeat (failures included).",
        "",
        "This directory is git-ignored (results/). Do not commit.",
    ]
    if run.judge_model_reported:
        lines.append(f"- judge_model_reported: {sorted(run.judge_model_reported)}")
    if agg is not None:
        g = agg["global"]
        ops = g["operational_attempt_metrics"]
        lines += [
            "",
            "## Headline results",
            "",
            f"- eligible cases: {g['eligible_case_count']}/{g['total_cases']}",
            f"- successful semantic repeats: "
            f"{ops['successful_semantic_repeats']}/{ops['planned_semantic_repeats']}",
            f"- total physical attempts: {ops['total_physical_attempts']} "
            f"(max possible {ops['max_possible_physical_attempts']})",
            f"- first attempt success rate: {ops['first_attempt_success_rate']}",
            f"- retry recovery rate: {ops['retry_recovery_rate']}",
            f"- overall score mean: {g['overall_score']['mean']}",
            f"- overall score median: {g['overall_score']['median']}",
        ]
    return "\n".join(lines) + "\n"
