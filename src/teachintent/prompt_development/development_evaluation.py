"""Prompt v0.2-rc.1 paired development evaluation (offline orchestration).

Compares two SIDES over the SAME frozen 30-case Pilot population:

    v0.1 side    Generator v0.1 + Prompt v0.1   (canonical, frozen)
    rc.1 side    Generator v0.1 + Prompt v0.2-rc.1  (candidate)

What is REUSED and never regenerated
------------------------------------

* **v0.1 generation** — the three canonical Pilot runs (A/B/C = 12/12/6).
* **v0.1 evaluation** — the finished Generator v0.1 baseline evaluation run
  (Protocol v0.2, ``20260830T095934Z``), loaded READ-ONLY from its artifacts.
  No Judge is ever called for the v0.1 side and nothing is re-evaluated.
* **rc.1 generation** — the finished candidate development run
  (``20260831-052126``), loaded READ-ONLY.
* **Evaluator v0.1** — called through the frozen Protocol v0.2 acquisition
  policy imported from :mod:`teachintent.generator_evaluation.baseline_v0_2`.
  The retry taxonomy, the 3-semantic-repeat design, the <= 3 physical-attempt
  policy and every aggregation formula are REUSED, never re-implemented.

The ONLY new Judge calls in this experiment are the **rc.1 semantic
evaluations**: 30 candidate plans x 3 semantic repeats = 90 planned semantic
evaluations, at most 3 physical attempts each (270 worst case).

Operational failures are NEVER converted into a semantic zero: a semantic
repeat that never produced a legal artifact contributes no score and shrinks
the denominator instead.

This produces DEVELOPMENT evidence, not held-out confirmatory evidence.
No PASS/FAIL threshold is defined anywhere in this module.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from ..generator_evaluation.baseline_v0_1 import (
    BLOCK_NAMES,
    CASE_COUNT,
    DIMENSION_LABELS,
    GENERATOR_VERSION,
    GENERATOR_VERSION_PROVENANCE,
    INTENTS,
    MIN_SUCCESSFUL_REPEATS,
    REPEATS,
    SOURCE_POPULATION_SHA256,
    CanonicalCase,
    _LABEL_TO_DIM,
    _canonical_utc_now,
    _sha256_file,
    _utc_run_id,
    _write_group_metrics_csv,
    block_metrics,
    build_population_records,
    case_critical_flags,
    case_dimension_means,
    case_eligible,
    case_overall_mean,
    compute_population_sha256,
    intent_metrics,
)
from ..generator_evaluation.baseline_v0_2 import (
    BASELINE_ATTEMPT_RETRY_ENABLED,
    EVALUATOR_RETRY_ENABLED,
    MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
    NON_RETRYABLE_FAILURE_TYPES,
    PLANNED_SEMANTIC_REPEATS,
    PROTOCOL_DOC_PATH,
    PROTOCOL_STATUS,
    PROTOCOL_VERSION,
    RETRYABLE_FAILURE_TYPES,
    RETRY_BACKOFF_SECONDS,
    BaselineRunV2,
    aggregate_v0_2,
    execute_baseline_run_v2,
)

__all__ = [
    # ---- Identity ----
    "BASELINE_PROMPT_VERSION",
    "CANDIDATE_PROMPT_VERSION",
    "BASELINE_EVALUATION_RUN_ID",
    "CANDIDATE_GENERATION_RUN_ID",
    "PRIMARY_DIMENSION",
    "SECONDARY_DIMENSION",
    "PROTECTED_DIMENSIONS",
    "TIE_TOLERANCE",
    "PER_BLOCK_EXPECTED",
    # ---- Frozen protocol constants re-exported for the runner CLI ----
    "CASE_COUNT",
    "REPEATS",
    "MIN_SUCCESSFUL_REPEATS",
    "PLANNED_SEMANTIC_REPEATS",
    "MAX_ATTEMPTS_PER_SEMANTIC_REPEAT",
    "MAX_POSSIBLE_PHYSICAL_ATTEMPTS",
    "RETRYABLE_FAILURE_TYPES",
    "NON_RETRYABLE_FAILURE_TYPES",
    "RESULTS_ROOT",
    "BASELINE_EVALUATION_ROOT",
    "CANDIDATE_GENERATION_ROOT",
    # ---- Errors ----
    "DevelopmentEvaluationError",
    # ---- Data types ----
    "BaselineSide",
    "CandidateIntegrity",
    "DevelopmentEvaluationRun",
    # ---- Loading / preparation (offline) ----
    "load_baseline_evaluation",
    "load_candidate_cases",
    "prepare_candidate_run",
    "prepare_development_evaluation",
    # ---- Execution ----
    "execute_candidate_evaluation",
    # ---- Paired comparison (pure) ----
    "case_pair_rows",
    "delta_stats",
    "dimension_paired_stats",
    "group_breakdown",
    "critical_flag_comparison",
    "build_paired_comparison",
    "build_development_summary",
    "build_development_manifest",
    # ---- Artifacts ----
    "write_paired_comparison_csv",
    "write_development_artifacts",
]

# ---------------------------------------------------------------------------
# Frozen side identities.
# ---------------------------------------------------------------------------
#: The v0.1 comparison side's prompt.
BASELINE_PROMPT_VERSION = "v0.1"
#: The candidate prompt under development.
CANDIDATE_PROMPT_VERSION = "v0.2-rc.1"

#: The FINISHED Protocol v0.2 baseline evaluation run (reused, never rerun).
BASELINE_EVALUATION_RUN_ID = "20260830T095934Z"
#: The FINISHED candidate development generation run (reused, never rerun).
CANDIDATE_GENERATION_RUN_ID = "20260831-052126"

_REPO_ROOT = Path(__file__).resolve().parents[3]

RESULTS_ROOT = _REPO_ROOT / "results" / "prompt_v0_2_rc1_development_evaluation"

BASELINE_EVALUATION_ROOT = (
    _REPO_ROOT
    / "results"
    / "generator_v0_1_baseline_evaluation_v0_2"
    / BASELINE_EVALUATION_RUN_ID
)

CANDIDATE_GENERATION_ROOT = (
    _REPO_ROOT
    / "results"
    / "prompt_v0_2_rc1_development"
    / CANDIDATE_GENERATION_RUN_ID
)

# ---------------------------------------------------------------------------
# Comparison design.
#
# D5 (Delivery Necessity / Sparsity) is the PRIMARY dimension — it is what
# Prompt v0.2-rc.1 was written to move. D4 (Instructional Adequacy) is
# SECONDARY; the target is "improve or remain stable". D1/D2/D3/D6 are
# PROTECTED: we look for systematic degradation, not for a gain.
#
# No numeric acceptance gate is defined for any of them (Section 11).
# ---------------------------------------------------------------------------
PRIMARY_DIMENSION = "D5"
SECONDARY_DIMENSION = "D4"
PROTECTED_DIMENSIONS: tuple[str, ...] = ("D1", "D2", "D3", "D6")

#: A paired delta is "tied" when it is exactly zero within this tolerance.
#: Case means are rounded to 4 dp by the frozen v0.1 reducer, so exact
#: equality between two identical means is well defined.
TIE_TOLERANCE = 1e-9

#: Block composition inherited from the frozen population: A/B/C = 12/12/6.
PER_BLOCK_EXPECTED: dict[str, int] = {"A": 12, "B": 12, "C": 6}

#: The candidate runner stores ``block`` as a slug ("block_a"); the frozen
#: evaluation side uses the single letter ("A").
_BLOCK_SLUG_TO_LETTER: dict[str, str] = {
    "block_a": "A",
    "block_b": "B",
    "block_c": "C",
}

_REQUIRED_ARTIFACTS = (
    "input.json",
    "metadata.json",
    "parsed.json",
    "prompt.json",
    "raw_response.txt",
    "validation.json",
)


class DevelopmentEvaluationError(RuntimeError):
    """Raised when the paired development comparison fails a pre-flight check."""


# ---------------------------------------------------------------------------
# Data types.
# ---------------------------------------------------------------------------
@dataclass
class BaselineSide:
    """The FINISHED v0.1 baseline evaluation result, loaded read-only.

    Nothing here is recomputed and no Judge is ever called for this side.
    """

    run_id: str
    root: str
    manifest: dict[str, Any]
    summary: dict[str, Any]
    #: case_id -> the frozen v0.2 ``case_diagnostics`` row for that case.
    case_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: case_id -> input.json SHA256 (from the frozen population fingerprint).
    input_sha256_by_case: dict[str, str] = field(default_factory=dict)
    #: block letter -> canonical Pilot run id.
    source_run_ids: dict[str, str] = field(default_factory=dict)
    case_ids: tuple[str, ...] = ()


@dataclass
class CandidateIntegrity:
    """Offline pre-flight report for the 30-case candidate generation run."""

    ok: bool = True
    messages: list[str] = field(default_factory=list)
    per_block_counts: dict[str, int] = field(default_factory=dict)
    total_cases: int = 0
    unique_case_ids: bool = False
    duplicate_case_ids: list[str] = field(default_factory=list)
    prompt_versions: list[str] = field(default_factory=list)
    generation_outcomes: list[str] = field(default_factory=list)
    restorable_cases: int = 0
    #: Full six-artifact population records for the candidate run.
    population_records: list[dict[str, str]] = field(default_factory=list)
    population_sha256: str = ""
    #: case_id -> input.json SHA256 (comparable with the v0.1 side).
    input_sha256_by_case: dict[str, str] = field(default_factory=dict)
    #: The candidate case ID set equals the v0.1 canonical population set.
    case_ids_exact_match: bool = False
    #: Every candidate input.json is byte-identical to the v0.1 population input.
    input_fingerprints_match: bool = False
    case_ids: tuple[str, ...] = ()


@dataclass
class DevelopmentEvaluationRun:
    """State for one paired development comparison run."""

    run_id: str
    started_at: str
    baseline: BaselineSide
    candidate_run: BaselineRunV2
    integrity: CandidateIntegrity
    completed_at: str | None = None
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------
def _round4(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _read_json(path: Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")


# ---------------------------------------------------------------------------
# Two-sided 95% t critical values (alpha = 0.05).
#
# scipy is deliberately not a dependency of this project, so the critical
# values are tabulated. df 1..30 are exact to 5 dp; larger df are interpolated
# in 1/df towards the normal limit, which is accurate to ~1e-4.
# ---------------------------------------------------------------------------
_T_CRITICAL_95_DF_1_30: tuple[float, ...] = (
    12.7062, 4.30265, 3.18245, 2.77645, 2.57058,
    2.44691, 2.36462, 2.30600, 2.26216, 2.22814,
    2.20099, 2.17881, 2.16037, 2.14479, 2.13145,
    2.11991, 2.10982, 2.10092, 2.09302, 2.08596,
    2.07961, 2.07387, 2.06866, 2.06390, 2.05954,
    2.05553, 2.05183, 2.04841, 2.04523, 2.04227,
)

#: Interpolation knots (1/df, t) for df > 30, ending at the normal limit.
_T_CRITICAL_95_KNOTS: tuple[tuple[float, float], ...] = (
    (1.0 / 30.0, 2.04227),
    (1.0 / 40.0, 2.02108),
    (1.0 / 60.0, 2.00030),
    (1.0 / 120.0, 1.97993),
    (0.0, 1.959964),
)


def _t_critical_95(df: int) -> float:
    """Two-sided 95% Student-t critical value for ``df`` degrees of freedom."""
    if df < 1:
        return float("nan")
    if df <= 30:
        return _T_CRITICAL_95_DF_1_30[df - 1]
    x = 1.0 / float(df)
    for (x0, y0), (x1, y1) in zip(
        _T_CRITICAL_95_KNOTS, _T_CRITICAL_95_KNOTS[1:]
    ):
        if x0 >= x >= x1:
            span = x0 - x1
            if span == 0.0:
                return y1
            return y0 + (y1 - y0) * ((x0 - x) / span)
    return _T_CRITICAL_95_KNOTS[-1][1]


# ---------------------------------------------------------------------------
# Baseline side: load the FINISHED v0.1 evaluation, read-only.
# ---------------------------------------------------------------------------
def load_baseline_evaluation(
    root: Path | str = BASELINE_EVALUATION_ROOT,
) -> BaselineSide:
    """Load the frozen Generator v0.1 baseline evaluation run (Protocol v0.2).

    Purely READ-ONLY: the v0.1 plans are not regenerated and the v0.1 Judge
    evaluations are not rerun. Raises :class:`DevelopmentEvaluationError` when
    the run is missing, incomplete, or is not the expected frozen run.
    """
    root = Path(root)
    manifest_path = root / "run_manifest.json"
    summary_path = root / "summary.json"

    if not root.is_dir():
        raise DevelopmentEvaluationError(
            f"baseline evaluation run directory missing: {root}"
        )
    for required in (manifest_path, summary_path):
        if not required.is_file():
            raise DevelopmentEvaluationError(f"missing artifact: {required}")

    manifest = _read_json(manifest_path)
    summary = _read_json(summary_path)

    run_id = manifest.get("run_id")
    if run_id != BASELINE_EVALUATION_RUN_ID:
        raise DevelopmentEvaluationError(
            f"baseline run_id={run_id!r} != expected {BASELINE_EVALUATION_RUN_ID!r}"
        )
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise DevelopmentEvaluationError(
            f"baseline protocol_version={manifest.get('protocol_version')!r} != "
            f"{PROTOCOL_VERSION!r}"
        )
    if manifest.get("dry_run"):
        raise DevelopmentEvaluationError(
            f"baseline run {run_id} is a dry-run; it carries no evaluations"
        )
    if manifest.get("prompt_version") != BASELINE_PROMPT_VERSION:
        raise DevelopmentEvaluationError(
            f"baseline prompt_version={manifest.get('prompt_version')!r} != "
            f"{BASELINE_PROMPT_VERSION!r}"
        )

    case_rows_list = summary.get("case_diagnostics")
    if not isinstance(case_rows_list, list) or not case_rows_list:
        raise DevelopmentEvaluationError(
            f"baseline summary carries no case_diagnostics: {summary_path}"
        )

    case_rows: dict[str, dict[str, Any]] = {}
    for row in case_rows_list:
        case_rows[row["case_id"]] = row
    if len(case_rows) != CASE_COUNT:
        raise DevelopmentEvaluationError(
            f"baseline case_diagnostics has {len(case_rows)} cases, "
            f"expected {CASE_COUNT}"
        )

    input_sha256_by_case: dict[str, str] = {}
    for record in manifest.get("source_population_records", []):
        input_sha256_by_case[record["case_id"]] = record["input_sha256"]

    source_run_ids: dict[str, str] = {}
    for source in manifest.get("source_runs", []):
        source_run_ids[source["block"]] = source["run_id"]

    return BaselineSide(
        run_id=run_id,
        root=str(root),
        manifest=manifest,
        summary=summary,
        case_rows=case_rows,
        input_sha256_by_case=input_sha256_by_case,
        source_run_ids=source_run_ids,
        case_ids=tuple(sorted(case_rows)),
    )


# ---------------------------------------------------------------------------
# Candidate side: load the FINISHED rc.1 generation run, read-only.
# ---------------------------------------------------------------------------
def load_candidate_cases(
    baseline: BaselineSide,
    root: Path | str = CANDIDATE_GENERATION_ROOT,
) -> tuple[list[CanonicalCase], CandidateIntegrity]:
    """Restore the 30 rc.1 Speech Plans from the finished generation run.

    Reads the candidate run directory only — no plan is regenerated and no
    repair is attempted. Every pre-flight violation is collected into
    :class:`CandidateIntegrity` rather than raising, so the dry-run can report
    the full picture before any Judge is called.
    """
    root = Path(root)
    integrity = CandidateIntegrity()
    problems: list[str] = []

    manifest_path = root / "run_manifest.json"
    if not root.is_dir():
        problems.append(f"candidate generation run directory missing: {root}")
        integrity.ok = False
        integrity.messages = problems
        return [], integrity
    if not manifest_path.is_file():
        problems.append(f"candidate run manifest missing: {manifest_path}")
        integrity.ok = False
        integrity.messages = problems
        return [], integrity

    manifest = _read_json(manifest_path)
    run_id = manifest.get("run_id")
    if run_id != CANDIDATE_GENERATION_RUN_ID:
        problems.append(
            f"candidate run_id={run_id!r} != expected "
            f"{CANDIDATE_GENERATION_RUN_ID!r}"
        )
    if manifest.get("prompt_version") != CANDIDATE_PROMPT_VERSION:
        problems.append(
            f"candidate prompt_version={manifest.get('prompt_version')!r} != "
            f"{CANDIDATE_PROMPT_VERSION!r}"
        )

    cases_dir = root / "cases"
    if not cases_dir.is_dir():
        problems.append(f"candidate cases directory missing: {cases_dir}")
        integrity.ok = False
        integrity.messages = problems
        return [], integrity

    cases: list[CanonicalCase] = []
    case_dirs = sorted(
        (p for p in cases_dir.iterdir() if p.is_dir()), key=lambda p: p.name
    )

    for case_dir in case_dirs:
        missing = [
            name
            for name in _REQUIRED_ARTIFACTS
            if not (case_dir / name).is_file()
        ]
        if missing:
            problems.append(f"{case_dir.name}: missing artifact(s) {missing}")
            continue

        metadata = _read_json(case_dir / "metadata.json")
        validation = _read_json(case_dir / "validation.json")
        prompt = _read_json(case_dir / "prompt.json")
        input_doc = _read_json(case_dir / "input.json")
        raw_response = (case_dir / "raw_response.txt").read_text(encoding="utf-8")

        case_id = metadata.get("case_id") or case_dir.name
        if case_id != case_dir.name:
            problems.append(
                f"{case_dir.name}: metadata case_id={case_id!r} != dir name"
            )

        # prompt_version must agree across metadata.json and prompt.json, and
        # must be the candidate — a silent fallback to v0.1 would invalidate
        # the whole comparison.
        prompt_version = prompt.get("prompt_version")
        if metadata.get("prompt_version") != prompt_version:
            problems.append(
                f"{case_id}: prompt_version mismatch "
                f"(metadata={metadata.get('prompt_version')!r}, "
                f"prompt.json={prompt_version!r})"
            )
        if prompt_version != CANDIDATE_PROMPT_VERSION:
            problems.append(
                f"{case_id}: prompt_version={prompt_version!r} != "
                f"{CANDIDATE_PROMPT_VERSION!r}"
            )

        outcome = validation.get("outcome")
        if outcome != "success":
            problems.append(
                f"{case_id}: candidate generation outcome={outcome!r} != 'success'"
            )

        block_slug = metadata.get("block") or ""
        block = _BLOCK_SLUG_TO_LETTER.get(block_slug)
        if block is None:
            problems.append(f"{case_id}: unknown block slug {block_slug!r}")
            continue

        intent = (input_doc.get("pedagogical_intent") or {}).get("primary")
        if intent not in INTENTS:
            problems.append(f"{case_id}: unknown intent {intent!r}")

        case = CanonicalCase(
            case_id=case_id,
            block=block,
            block_name=BLOCK_NAMES[block],
            intent=intent if intent in INTENTS else "",
            source_run_id=run_id or "",
            source_path=str(case_dir),
            input_doc=input_doc,
            raw_response=raw_response,
            prompt_version=prompt_version or "",
            generator_version=GENERATOR_VERSION,
            requested_model=metadata.get("requested_model"),
            reported_model=metadata.get("reported_model"),
            generation_outcome=outcome or "",
        )
        cases.append(case)
        integrity.restorable_cases += 1
        integrity.per_block_counts[block] = (
            integrity.per_block_counts.get(block, 0) + 1
        )

    # ---- Population-level checks ----
    ids = [c.case_id for c in cases]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    integrity.total_cases = len(cases)
    integrity.duplicate_case_ids = duplicates
    integrity.unique_case_ids = not duplicates
    integrity.prompt_versions = sorted({c.prompt_version for c in cases})
    integrity.generation_outcomes = sorted({c.generation_outcome for c in cases})
    integrity.case_ids = tuple(sorted(ids))

    if duplicates:
        problems.append(f"duplicate case_id(s): {duplicates}")
    if len(cases) != CASE_COUNT:
        problems.append(f"expected {CASE_COUNT} candidate cases, found {len(cases)}")
    for block, expected in PER_BLOCK_EXPECTED.items():
        actual = integrity.per_block_counts.get(block, 0)
        if actual != expected:
            problems.append(
                f"block {block}: expected {expected} cases, found {actual}"
            )
    if integrity.prompt_versions not in ([], [CANDIDATE_PROMPT_VERSION]):
        problems.append(
            f"unexpected prompt_version set: {integrity.prompt_versions}"
        )
    if integrity.generation_outcomes not in ([], ["success"]):
        problems.append(
            f"unexpected generation outcome set: {integrity.generation_outcomes}"
        )

    # ---- Cross-side identity: same population, byte-identical inputs ----
    integrity.case_ids_exact_match = set(ids) == set(baseline.case_ids) and not duplicates
    if not integrity.case_ids_exact_match:
        missing_ids = sorted(set(baseline.case_ids) - set(ids))
        extra_ids = sorted(set(ids) - set(baseline.case_ids))
        problems.append(
            "candidate case IDs do not exactly match the v0.1 canonical "
            f"population (missing={missing_ids}, extra={extra_ids}, "
            f"duplicates={duplicates})"
        )

    integrity.population_records = build_population_records(cases)
    integrity.population_sha256 = compute_population_sha256(
        integrity.population_records
    )
    for record in integrity.population_records:
        integrity.input_sha256_by_case[record["case_id"]] = record["input_sha256"]

    mismatched_inputs = sorted(
        cid
        for cid, sha in integrity.input_sha256_by_case.items()
        if baseline.input_sha256_by_case.get(cid) != sha
    )
    integrity.input_fingerprints_match = not mismatched_inputs
    if mismatched_inputs:
        problems.append(
            "candidate input.json is not byte-identical to the v0.1 population "
            f"for case(s): {mismatched_inputs}"
        )

    integrity.messages = problems
    integrity.ok = not problems
    return cases, integrity


def prepare_candidate_run(
    cases: Sequence[CanonicalCase],
    integrity: CandidateIntegrity,
    *,
    manifest: dict[str, Any] | None = None,
) -> BaselineRunV2:
    """Build the Protocol v0.2 run object for the rc.1 evaluation.

    This is the SAME run type the frozen baseline uses, so the rc.1 side is
    executed and aggregated by the frozen v0.2 code path — not by a copy.
    """
    manifest = manifest or {}
    source_runs = [
        {
            "block": "candidate",
            "block_name": "prompt_v0_2_rc1_development",
            "run_id": CANDIDATE_GENERATION_RUN_ID,
            "path": str(CANDIDATE_GENERATION_ROOT),
            "dataset_path": None,
            "expected_cases": CASE_COUNT,
            "actual_cases": integrity.total_cases,
            "pass_count": manifest.get("pass_count"),
            "fail_count": manifest.get("fail_count"),
            "started_at": manifest.get("started_at"),
            "finished_at": manifest.get("finished_at"),
            "requested_model": (manifest.get("actual_conditions") or {}).get("model"),
            "temperature": (manifest.get("actual_conditions") or {}).get(
                "temperature"
            ),
        }
    ]

    return BaselineRunV2(
        run_id=_utc_run_id(),
        started_at=_canonical_utc_now(),
        dry_run=True,
        protocol_version=PROTOCOL_VERSION,
        protocol_status=PROTOCOL_STATUS,
        protocol_document_sha256=(
            _sha256_file(PROTOCOL_DOC_PATH) if PROTOCOL_DOC_PATH.is_file() else ""
        ),
        source_runs=source_runs,
        integrity=None,
        cases=list(cases),
        semantic_repeats_per_case=REPEATS,
        planned_semantic_repeats=PLANNED_SEMANTIC_REPEATS,
        max_attempts_per_semantic_repeat=MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
        max_possible_physical_attempts=MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
        generator_version=GENERATOR_VERSION,
        generator_version_provenance=(
            GENERATOR_VERSION_PROVENANCE
            + "; identical frozen Generator stack, only prompt_version differs"
        ),
        prompt_version=CANDIDATE_PROMPT_VERSION,
        prompt_version_provenance=(
            "artifact_directly_recorded; cases/<case_id>/prompt.json and "
            "metadata.json both record prompt_version = v0.2-rc.1 and are "
            "asserted per case by load_candidate_cases"
        ),
        source_population_sha256=integrity.population_sha256,
        source_population_sha256_expected=SOURCE_POPULATION_SHA256,
        # The FULL six-artifact fingerprint legitimately differs: the rc.1 run
        # produced new raw_response / parsed / prompt / metadata artifacts over
        # the SAME inputs. Population identity is asserted through
        # ``input_fingerprints_match``, not through this field.
        source_population_sha256_match=False,
    )


def prepare_development_evaluation(
    *,
    baseline_root: Path | str = BASELINE_EVALUATION_ROOT,
    candidate_root: Path | str = CANDIDATE_GENERATION_ROOT,
) -> DevelopmentEvaluationRun:
    """Offline pre-flight for BOTH sides. Never calls the Judge.

    Raises :class:`DevelopmentEvaluationError` when any cross-side identity
    check fails, so a broken population can never reach a Judge call.
    """
    baseline = load_baseline_evaluation(baseline_root)
    cases, integrity = load_candidate_cases(baseline, candidate_root)

    if not integrity.ok:
        detail = "\n  - ".join(integrity.messages)
        raise DevelopmentEvaluationError(
            "candidate population pre-flight failed:\n  - " + detail
        )

    candidate_manifest = _read_json(Path(candidate_root) / "run_manifest.json")
    candidate_run = prepare_candidate_run(cases, integrity, manifest=candidate_manifest)

    return DevelopmentEvaluationRun(
        run_id=_utc_run_id(),
        started_at=_canonical_utc_now(),
        baseline=baseline,
        candidate_run=candidate_run,
        integrity=integrity,
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# Execution: the ONLY new Judge calls in this experiment.
# ---------------------------------------------------------------------------
def execute_candidate_evaluation(
    run: DevelopmentEvaluationRun,
    judge,
    *,
    max_attempts: int = MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    sleep_fn: Callable[[float], None] | None = None,
) -> None:
    """Evaluate the 30 rc.1 plans under the frozen Protocol v0.2 policy.

    Delegates verbatim to :func:`execute_baseline_run_v2`, so the semantic
    design (3 repeats), the attempt policy (<= 3 physical attempts), the
    retryable taxonomy and the reducer are literally the frozen code.

    The v0.1 side is never touched here.
    """
    kwargs: dict[str, Any] = {}
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    execute_baseline_run_v2(
        run.candidate_run, judge, max_attempts=max_attempts, **kwargs
    )
    run.dry_run = False
    run.completed_at = _canonical_utc_now()


# ---------------------------------------------------------------------------
# Paired comparison (pure; no API).
# ---------------------------------------------------------------------------
def case_pair_rows(
    run: DevelopmentEvaluationRun,
) -> list[dict[str, Any]]:
    """One row per case, carrying both sides' per-case metrics.

    A case enters the paired comparison only when BOTH sides are eligible
    (``>= MIN_SUCCESSFUL_REPEATS`` successful semantic repeats). Success on one
    side never triggers a rerun of the other.
    """
    records = run.candidate_run.records
    rows: list[dict[str, Any]] = []

    for case in sorted(run.candidate_run.cases, key=lambda c: c.case_id):
        cid = case.case_id
        baseline_row = run.baseline.case_rows.get(cid)
        if baseline_row is None:  # pragma: no cover — pre-flight guarantees it
            raise DevelopmentEvaluationError(
                f"case {cid} absent from the v0.1 baseline evaluation"
            )

        v01_eligible = bool(baseline_row.get("eligible"))
        rc1_eligible = case_eligible(records, cid)

        v01_means = baseline_row.get("dimension_means") or None
        # ``case_dimension_means`` keys by the long ``DIMENSION_IDS`` names
        # (e.g. ``delivery_necessity_sparsity``); the frozen baseline
        # ``dimension_means`` uses the short labels (``D5``). Relabel so the two
        # sides are directly comparable.
        rc1_means_long = case_dimension_means(records, cid)
        rc1_means = (
            None
            if rc1_means_long is None
            else {
                label: rc1_means_long[dim]
                for label, dim in _LABEL_TO_DIM.items()
            }
        )

        pair_eligible = v01_eligible and rc1_eligible
        if pair_eligible:
            exclusion_reason = None
        elif not v01_eligible and not rc1_eligible:
            exclusion_reason = "both_sides_ineligible"
        elif not v01_eligible:
            exclusion_reason = "v0_1_side_ineligible"
        else:
            exclusion_reason = "rc_1_side_ineligible"

        rc1_flags = list(case_critical_flags(records, cid))
        v01_flags = list(baseline_row.get("critical_flags") or ())

        row: dict[str, Any] = {
            "case_id": cid,
            "block": case.block,
            "block_name": case.block_name,
            "intent": case.intent,
            "v0_1_eligible": v01_eligible,
            "rc_1_eligible": rc1_eligible,
            "pair_eligible": pair_eligible,
            "exclusion_reason": exclusion_reason,
            "v0_1_successful_repeats": baseline_row.get("successful_repeats"),
            "rc_1_successful_repeats": len(
                [r for r in records if r.case_id == cid and r.scores is not None]
            ),
            "v0_1_overall_mean": baseline_row.get("overall_mean"),
            "rc_1_overall_mean": case_overall_mean(records, cid),
            "v0_1_critical_flags": v01_flags,
            "rc_1_critical_flags": rc1_flags,
            "new_flags": sorted(set(rc1_flags) - set(v01_flags)),
            "removed_flags": sorted(set(v01_flags) - set(rc1_flags)),
        }
        for label in DIMENSION_LABELS:
            v01_value = None if v01_means is None else v01_means.get(label)
            rc1_value = None if rc1_means is None else rc1_means.get(label)
            row[f"v0_1_{label}"] = v01_value
            row[f"rc_1_{label}"] = rc1_value
            # A missing side is NOT a zero: the delta is simply undefined.
            row[f"delta_{label}"] = (
                None
                if not pair_eligible or v01_value is None or rc1_value is None
                else _round4(rc1_value - v01_value)
            )
        row["delta_overall_mean"] = (
            None
            if not pair_eligible
            or row["v0_1_overall_mean"] is None
            or row["rc_1_overall_mean"] is None
            else _round4(row["rc_1_overall_mean"] - row["v0_1_overall_mean"])
        )
        rows.append(row)

    return rows


def delta_stats(values: Sequence[float]) -> dict[str, Any]:
    """mean / median / 95% CI / improved-tied-worsened for paired deltas.

    ``values`` are per-case deltas (rc.1 minus v0.1). Undefined deltas are
    excluded by the caller — a failed semantic repeat never contributes a zero.
    """
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "stdev": None,
            "ci95_low": None,
            "ci95_high": None,
            "ci95_method": "student_t",
            "improved": 0,
            "tied": 0,
            "worsened": 0,
        }

    mean = statistics.fmean(vals)
    median = statistics.median(vals)
    stdev = statistics.stdev(vals) if n >= 2 else 0.0

    if n >= 2 and stdev > 0.0:
        half = _t_critical_95(n - 1) * stdev / math.sqrt(n)
        ci_low: float | None = mean - half
        ci_high: float | None = mean + half
    elif n >= 2:
        ci_low = ci_high = mean
    else:
        ci_low = ci_high = None

    improved = sum(1 for v in vals if v > TIE_TOLERANCE)
    worsened = sum(1 for v in vals if v < -TIE_TOLERANCE)
    tied = n - improved - worsened

    return {
        "n": n,
        "mean": _round4(mean),
        "median": _round4(median),
        "stdev": _round4(stdev),
        "ci95_low": _round4(ci_low),
        "ci95_high": _round4(ci_high),
        "ci95_method": "student_t",
        "improved": improved,
        "tied": tied,
        "worsened": worsened,
    }


def dimension_paired_stats(
    rows: Sequence[dict[str, Any]],
    dimension: str = PRIMARY_DIMENSION,
) -> dict[str, Any]:
    """Paired delta statistics for one dimension over pair-eligible cases."""
    deltas = [
        r[f"delta_{dimension}"]
        for r in rows
        if r["pair_eligible"] and r[f"delta_{dimension}"] is not None
    ]
    v01_values = [
        r[f"v0_1_{dimension}"]
        for r in rows
        if r["pair_eligible"] and r[f"v0_1_{dimension}"] is not None
    ]
    rc1_values = [
        r[f"rc_1_{dimension}"]
        for r in rows
        if r["pair_eligible"] and r[f"rc_1_{dimension}"] is not None
    ]
    stats = delta_stats(deltas)
    stats.update(
        {
            "dimension": dimension,
            "v0_1_mean": _round4(statistics.fmean(v01_values)) if v01_values else None,
            "rc_1_mean": _round4(statistics.fmean(rc1_values)) if rc1_values else None,
        }
    )
    return stats


def group_breakdown(
    rows: Sequence[dict[str, Any]],
    key: str,
) -> dict[str, dict[str, Any]]:
    """Per-group (intent / block) v0.1 mean, rc.1 mean and paired delta.

    Groups are reported even when a group has no pair-eligible case, so a
    coverage gap is visible rather than silently absent.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row[key], []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for name in sorted(groups):
        members = groups[name]
        pairs = [r for r in members if r["pair_eligible"]]
        entry: dict[str, Any] = {
            "n_total": len(members),
            "n_pair_eligible": len(pairs),
            "excluded_case_ids": sorted(
                r["case_id"] for r in members if not r["pair_eligible"]
            ),
        }
        for label in DIMENSION_LABELS:
            v01 = [
                r[f"v0_1_{label}"] for r in pairs if r[f"v0_1_{label}"] is not None
            ]
            rc1 = [
                r[f"rc_1_{label}"] for r in pairs if r[f"rc_1_{label}"] is not None
            ]
            deltas = [
                r[f"delta_{label}"] for r in pairs if r[f"delta_{label}"] is not None
            ]
            entry[label] = {
                "v0_1_mean": _round4(statistics.fmean(v01)) if v01 else None,
                "rc_1_mean": _round4(statistics.fmean(rc1)) if rc1 else None,
                "paired_delta": delta_stats(deltas),
            }
        out[name] = entry
    return out


def critical_flag_comparison(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """v0.1 flags vs rc.1 flags over pair-eligible cases.

    Flags are reported as flags. They are never converted into a score.
    """
    pairs = [r for r in rows if r["pair_eligible"]]

    v01_counts: dict[str, int] = {}
    rc1_counts: dict[str, int] = {}
    new_counts: dict[str, int] = {}
    removed_counts: dict[str, int] = {}

    for row in pairs:
        for flag in row["v0_1_critical_flags"]:
            v01_counts[flag] = v01_counts.get(flag, 0) + 1
        for flag in row["rc_1_critical_flags"]:
            rc1_counts[flag] = rc1_counts.get(flag, 0) + 1
        for flag in row["new_flags"]:
            new_counts[flag] = new_counts.get(flag, 0) + 1
        for flag in row["removed_flags"]:
            removed_counts[flag] = removed_counts.get(flag, 0) + 1

    return {
        "n_pair_eligible_cases": len(pairs),
        "v0_1_flag_counts": {k: v01_counts[k] for k in sorted(v01_counts)},
        "rc_1_flag_counts": {k: rc1_counts[k] for k in sorted(rc1_counts)},
        "new_flags_introduced_by_rc_1": {
            k: new_counts[k] for k in sorted(new_counts)
        },
        "flags_removed_by_rc_1": {
            k: removed_counts[k] for k in sorted(removed_counts)
        },
        "cases_with_new_flags": sorted(
            r["case_id"] for r in pairs if r["new_flags"]
        ),
        "cases_with_removed_flags": sorted(
            r["case_id"] for r in pairs if r["removed_flags"]
        ),
        "note": (
            "Critical flags are reported as flags and are never converted "
            "into a score."
        ),
    }


def build_paired_comparison(
    run: DevelopmentEvaluationRun,
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """The full paired comparison block (Sections 5-11)."""
    total = len(rows)
    v01_eligible = sum(1 for r in rows if r["v0_1_eligible"])
    rc1_eligible = sum(1 for r in rows if r["rc_1_eligible"])
    pairs = [r for r in rows if r["pair_eligible"]]

    return {
        # ---- Coverage (Section 5) ----
        "coverage": {
            "total_cases": total,
            "v0_1_eligible": v01_eligible,
            "rc_1_eligible": rc1_eligible,
            "pair_eligible": len(pairs),
            "pair_coverage": (
                _round4(len(pairs) / total) if total else None
            ),
            "excluded_case_ids": sorted(
                r["case_id"] for r in rows if not r["pair_eligible"]
            ),
            "exclusions": [
                {
                    "case_id": r["case_id"],
                    "block": r["block"],
                    "intent": r["intent"],
                    "v0_1_eligible": r["v0_1_eligible"],
                    "rc_1_eligible": r["rc_1_eligible"],
                    "exclusion_reason": r["exclusion_reason"],
                    "v0_1_successful_repeats": r["v0_1_successful_repeats"],
                    "rc_1_successful_repeats": r["rc_1_successful_repeats"],
                }
                for r in rows
                if not r["pair_eligible"]
            ],
            "eligibility_rule": (
                f"a case is eligible on a side iff it has >= "
                f"{MIN_SUCCESSFUL_REPEATS} successful semantic repeats; a case "
                f"is pair-eligible iff BOTH sides are eligible. No side is ever "
                f"rerun to create a pair."
            ),
            "v0_1_side_rerun": False,
            "v0_1_side_reevaluated": False,
        },
        # ---- Primary (Section 6) ----
        "primary": {
            "dimension": PRIMARY_DIMENSION,
            "label": "Delivery Necessity / Sparsity",
            "target": "clear positive improvement",
            "threshold": None,
            "threshold_note": (
                "No arbitrary PASS threshold is set. The 95% CI and the "
                "improved/tied/worsened split are the evidence."
            ),
            **dimension_paired_stats(rows, PRIMARY_DIMENSION),
        },
        # ---- Secondary (Section 7) ----
        "secondary": {
            "dimension": SECONDARY_DIMENSION,
            "label": "Instructional Adequacy",
            "target": "improve or remain stable",
            "threshold": None,
            **dimension_paired_stats(rows, SECONDARY_DIMENSION),
        },
        # ---- Protected (Section 8) ----
        "protected": {
            dimension: dimension_paired_stats(rows, dimension)
            for dimension in PROTECTED_DIMENSIONS
        },
        "protected_note": (
            "We look for meaningful systematic degradation on D1/D2/D3/D6. "
            "No hard numeric gate (such as -0.10) is imposed by design."
        ),
        # ---- Breakdown (Section 9) ----
        "breakdown": {
            "by_intent": group_breakdown(rows, "intent"),
            "by_block": group_breakdown(rows, "block"),
            "focus": [
                "explanation D4/D5",
                "scaffolding D5",
                "supportive_feedback D5",
                "hard/adversarial Block C",
            ],
        },
        # ---- Critical flags (Section 10) ----
        "critical_flags": critical_flag_comparison(rows),
        # ---- Interpretation framing (Section 11) ----
        "interpretation": {
            "kind": "development_evidence",
            "is_confirmatory": False,
            "verdict": None,
            "questions": [
                "Primary: does D5 show a clear positive improvement?",
                "Secondary: does D4 improve or remain stable?",
                "Protected: is there systematic degradation on D1/D2/D3/D6?",
                "Coverage: is paired coverage sufficient to support a judgement?",
                "Case diagnostics: which cases improved or regressed markedly?",
            ],
            "note": (
                "This is development evidence, not held-out confirmatory "
                "evidence. No mechanical PASS/FAIL verdict is produced."
            ),
        },
    }


def _candidate_aggregate(run: DevelopmentEvaluationRun) -> dict[str, Any]:
    """Candidate-side metrics via the frozen v0.2 aggregation code path."""
    return aggregate_v0_2(run.candidate_run)


def build_development_manifest(run: DevelopmentEvaluationRun) -> dict[str, Any]:
    """run_manifest.json for the paired development evaluation run."""
    baseline_manifest = run.baseline.manifest
    cand = run.candidate_run

    return {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        # ---- Population ----
        "baseline_population": CASE_COUNT,
        "candidate_population": run.integrity.total_cases,
        "case_ids_exact_match": run.integrity.case_ids_exact_match,
        "unique_case_ids": run.integrity.unique_case_ids,
        "per_block_case_counts": run.integrity.per_block_counts,
        "input_fingerprints_match": run.integrity.input_fingerprints_match,
        # ---- Both source runs are FINISHED runs, reused read-only ----
        "baseline_generation_runs": baseline_manifest.get("source_run_ids", []),
        "baseline_evaluation_run": run.baseline.run_id,
        "candidate_generation_run": CANDIDATE_GENERATION_RUN_ID,
        "v0_1_generation_rerun": False,
        "v0_1_evaluation_rerun": False,
        # ---- Frozen protocol identity ----
        "protocol_version": cand.protocol_version,
        "protocol_status": cand.protocol_status,
        "protocol_document_path": str(PROTOCOL_DOC_PATH),
        "protocol_document_sha256": cand.protocol_document_sha256,
        # ---- Two sides ----
        "sides": {
            "v0_1": {
                "generator_version": baseline_manifest.get("generator_version"),
                "prompt_version": baseline_manifest.get("prompt_version"),
                "source": "frozen Generator v0.1 baseline evaluation run "
                "(reused read-only)",
            },
            "v0_2_rc_1": {
                "generator_version": cand.generator_version,
                "prompt_version": cand.prompt_version,
                "source": "candidate development generation run "
                f"{CANDIDATE_GENERATION_RUN_ID} (reused read-only), "
                "evaluated in this run",
            },
        },
        # ---- Frozen Judge provenance (identical on both sides) ----
        "evaluator_version": baseline_manifest.get("evaluator_version"),
        "judge_prompt_version": baseline_manifest.get("judge_prompt_version"),
        "judge_prompt_sha256": baseline_manifest.get("judge_prompt_sha256"),
        "judge_provider": cand.judge_provider
        or baseline_manifest.get("judge_provider"),
        "judge_model_requested": cand.judge_model_requested
        or baseline_manifest.get("judge_model_requested"),
        "judge_model_reported": list(cand.judge_model_reported),
        "temperature": baseline_manifest.get("temperature"),
        "structured_output_enabled": baseline_manifest.get(
            "structured_output_enabled"
        ),
        "self_repair_enabled": baseline_manifest.get("self_repair_enabled"),
        # ---- Retry policy: imported verbatim from Protocol v0.2 ----
        "evaluator_retry_enabled": EVALUATOR_RETRY_ENABLED,
        "attempt_retry_enabled": BASELINE_ATTEMPT_RETRY_ENABLED,
        "max_attempts_per_semantic_repeat": MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
        "retryable_failure_types": list(RETRYABLE_FAILURE_TYPES),
        "non_retryable_failure_types": list(NON_RETRYABLE_FAILURE_TYPES),
        "retry_backoff_policy": {
            failure_type: list(values)
            for failure_type, values in RETRY_BACKOFF_SECONDS.items()
        },
        "retry_policy_source": (
            "docs/generator_v0.1_evaluation_protocol_v0.2.md (Frozen) via "
            "teachintent.generator_evaluation.baseline_v0_2 — reused, not "
            "redesigned"
        ),
        # ---- Design ----
        "semantic_repeats_per_case": cand.semantic_repeats_per_case,
        "planned_candidate_semantic_evaluations": cand.planned_semantic_repeats,
        "maximum_candidate_physical_judge_calls": cand.max_possible_physical_attempts,
        "actual_candidate_physical_attempts": sum(
            r.attempt_count for r in cand.repeat_results
        ),
        "candidate_successful_semantic_repeats": sum(
            1 for r in cand.repeat_results if r.semantic_repeat_success
        ),
        "candidate_failed_semantic_repeats": sum(
            1 for r in cand.repeat_results if not r.semantic_repeat_success
        ),
    }


def build_development_summary(
    run: DevelopmentEvaluationRun,
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """summary.json: both sides' metrics + the paired comparison."""
    cand = run.candidate_run
    agg = _candidate_aggregate(run) if cand.records else None

    summary: dict[str, Any] = {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        "baseline_evaluation_run": run.baseline.run_id,
        "candidate_generation_run": CANDIDATE_GENERATION_RUN_ID,
        "case_ids_exact_match": run.integrity.case_ids_exact_match,
        "input_fingerprints_match": run.integrity.input_fingerprints_match,
        "evaluator_version": run.baseline.manifest.get("evaluator_version"),
        "judge_prompt_version": run.baseline.manifest.get("judge_prompt_version"),
        "judge_provider": cand.judge_provider
        or run.baseline.manifest.get("judge_provider"),
        "judge_model_requested": cand.judge_model_requested
        or run.baseline.manifest.get("judge_model_requested"),
        "judge_model_reported": list(cand.judge_model_reported),
        "temperature": run.baseline.manifest.get("temperature"),
        "structured_output_enabled": run.baseline.manifest.get(
            "structured_output_enabled"
        ),
        "self_repair_enabled": run.baseline.manifest.get("self_repair_enabled"),
        "evaluator_retry_enabled": EVALUATOR_RETRY_ENABLED,
        "attempt_retry_enabled": BASELINE_ATTEMPT_RETRY_ENABLED,
        "max_attempts_per_semantic_repeat": MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
        "semantic_repeats_per_case": cand.semantic_repeats_per_case,
        "planned_candidate_semantic_evaluations": cand.planned_semantic_repeats,
        "maximum_candidate_physical_judge_calls": (
            cand.max_possible_physical_attempts
        ),
        "verdict": None,
        "verdict_note": (
            "Prompt v0.2-rc.1 paired development comparison. Development "
            "evidence only — no PASS/FAIL threshold is defined."
        ),
    }

    if agg is not None:
        summary.update(
            {
                "candidate_side_metrics": {
                    "global": agg["global"],
                    "intent": agg["intent"],
                    "block": agg["block"],
                    "cases": agg["cases"],
                },
                "paired_comparison": build_paired_comparison(run, rows),
                "paired_case_rows": list(rows),
            }
        )
    else:
        summary["candidate_side_metrics"] = None
        summary["paired_comparison"] = None

    return summary


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------
_PAIRED_CSV_HEADER: tuple[str, ...] = (
    (
        "case_id",
        "block",
        "intent",
        "pair_eligible",
        "v0_1_eligible",
        "rc_1_eligible",
        "exclusion_reason",
    )
    + tuple(f"v0_1_{label}" for label in DIMENSION_LABELS)
    + tuple(f"rc_1_{label}" for label in DIMENSION_LABELS)
    + tuple(f"delta_{label}" for label in DIMENSION_LABELS)
    + (
        "v0_1_overall_mean",
        "rc_1_overall_mean",
        "delta_overall_mean",
        "v0_1_successful_repeats",
        "rc_1_successful_repeats",
        "v0_1_critical_flags",
        "rc_1_critical_flags",
        "new_flags",
        "removed_flags",
    )
)


def write_paired_comparison_csv(
    path: Path,
    rows: Sequence[dict[str, Any]],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(_PAIRED_CSV_HEADER))
        for row in rows:
            writer.writerow(
                [
                    row["case_id"],
                    row["block"],
                    row["intent"],
                    row["pair_eligible"],
                    row["v0_1_eligible"],
                    row["rc_1_eligible"],
                    row["exclusion_reason"] or "",
                ]
                + [
                    "" if row[f"v0_1_{label}"] is None else row[f"v0_1_{label}"]
                    for label in DIMENSION_LABELS
                ]
                + [
                    "" if row[f"rc_1_{label}"] is None else row[f"rc_1_{label}"]
                    for label in DIMENSION_LABELS
                ]
                + [
                    "" if row[f"delta_{label}"] is None else row[f"delta_{label}"]
                    for label in DIMENSION_LABELS
                ]
                + [
                    ""
                    if row["v0_1_overall_mean"] is None
                    else row["v0_1_overall_mean"],
                    ""
                    if row["rc_1_overall_mean"] is None
                    else row["rc_1_overall_mean"],
                    ""
                    if row["delta_overall_mean"] is None
                    else row["delta_overall_mean"],
                    row["v0_1_successful_repeats"],
                    row["rc_1_successful_repeats"],
                    "|".join(row["v0_1_critical_flags"]),
                    "|".join(row["rc_1_critical_flags"]),
                    "|".join(row["new_flags"]),
                    "|".join(row["removed_flags"]),
                ]
            )


def write_development_artifacts(
    run: DevelopmentEvaluationRun,
    out_dir: Path | str,
) -> None:
    """Write the paired development evaluation artifact set.

    In dry-run mode the candidate side has no evaluations, so only the
    manifest and summary (with ``null`` metrics) are written.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = case_pair_rows(run) if run.candidate_run.records else []

    _write_json(out_dir / "run_manifest.json", build_development_manifest(run))
    _write_json(out_dir / "summary.json", build_development_summary(run, rows))

    if rows:
        agg = _candidate_aggregate(run)
        from ..generator_evaluation.baseline_v0_2 import (
            _write_case_metrics_csv_v2,
        )

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
        write_paired_comparison_csv(out_dir / "paired_comparison.csv", rows)

    evaluations = out_dir / "evaluations.jsonl"
    if run.candidate_run.raw_evaluations:
        with evaluations.open("w", encoding="utf-8") as handle:
            for record in run.candidate_run.raw_evaluations:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
