"""Frozen Diagnostic Protocol v0.2 — confirmatory constants, metadata, integrity, and metrics.

This module implements the frozen semantics of
``docs/evaluator_diagnostic_protocol_v0.2.md`` (the authoritative methodological
specification). It is experiment-side code only and MUST NOT modify any frozen
component (Evaluator v0.1, Generator v0.1, Judge Prompt v0.1, the two Schemas,
the holdout dataset, or the protocol itself).

Key distinctions from Protocol v0.1 (implemented in ``metrics.py``):

* the dimension partition (primary / allowed-collateral / protected) is inherited
  from the frozen family coupling matrix (Section 9), NOT from per-pair
  ``target_dimensions``;
* Protected-Dimension MAE uses the MICRO-average over all eligible
  (pair, protected-dimension) shifts (Section 15) — no family averaging / weighting;
* repeatability is computed per (pair, variant, dimension) over all unordered
  successful repeat pairs (Section 17);
* semantic eligibility requires >= 2 successful repeats per variant and BOTH
  variants eligible (Section 12);
* critical flags use strict-majority over successful degraded repeats
  (Section 19), with reference-side flags reported separately;
* the six acceptance criteria are evaluated jointly for Semantic Validation
  PASS / FAIL (Section 22).

All functions are pure and deterministic; none call the judge or any API.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Sequence

from ..evaluator.rubric import CRITICAL_FLAGS, DIMENSION_IDS
from .dataset import DIAGNOSTIC_FAMILIES, load_diagnostic_pairs

__all__ = [
    # Paths / frozen hashes
    "PROTOCOL_VERSION",
    "CONFIRMATORY_DATASET_PATH",
    "FREEZE_RECORD_PATH",
    "PROTOCOL_METADATA_PATH",
    "PROTOCOL_DOC_PATH",
    "CONFIRMATORY_DATASET_SHA256",
    "DEVELOPMENT_DATASET_SHA256",
    # Frozen judge condition
    "FROZEN_JUDGE_PROVIDER",
    "FROZEN_JUDGE_MODEL_REQUESTED",
    "FROZEN_JUDGE_BASE_URL",
    "FROZEN_TEMPERATURE",
    "FROZEN_STRUCTURED_OUTPUT_ENABLED",
    "FROZEN_RETRY_ENABLED",
    "FROZEN_SELF_REPAIR_ENABLED",
    # Experiment shape
    "PAIR_COUNT",
    "REPEATS",
    "EXPECTED_CALLS",
    "THEORETICAL_SCORE_SERIES",
    "MIN_SUCCESSFUL_REPEATS",
    # Thresholds
    "PRIMARY_DIRECTIONAL_ACCURACY_THRESHOLD",
    "MEAN_PRIMARY_DROP_THRESHOLD",
    "PROTECTED_MAE_THRESHOLD",
    "WITHIN_ONE_REPEATABILITY_THRESHOLD",
    "SEMANTIC_COVERAGE_THRESHOLD",
    "PER_FAMILY_MIN_ELIGIBLE",
    # Data types
    "FamilyPartition",
    "ConfirmatoryRecord",
    "IntegrityReport",
    "PrimaryDirectionalAccuracy",
    "MeanPrimaryTargetedDrop",
    "ProtectedDimensionMAE",
    "CollateralDiagnostics",
    "ConfirmatoryRepeatability",
    "SemanticCoverage",
    "ConfirmatoryFlagDiagnostics",
    "OperationalReliability",
    "SemanticValidationResult",
    # Metadata / integrity
    "load_protocol_metadata",
    "family_partition",
    "verify_dataset_integrity",
    "load_freeze_record",
    # Eligibility + means
    "successful_repeat_count",
    "variant_eligible",
    "pair_eligible",
    "variant_mean_scores",
    # Metrics
    "primary_directional_accuracy",
    "mean_primary_targeted_drop",
    "protected_dimension_mae",
    "collateral_diagnostics",
    "confirmatory_repeatability",
    "semantic_pair_coverage",
    "confirmatory_flag_diagnostics",
    "operational_reliability",
    "evaluate_semantic_validation",
    "family_metrics",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CASES_DIR = _REPO_ROOT / "cases" / "evaluator_diagnostic"

PROTOCOL_VERSION = "v0.2"

CONFIRMATORY_DATASET_PATH = _CASES_DIR / "diagnostic_pairs_v0.2_holdout.jsonl"
FREEZE_RECORD_PATH = _CASES_DIR / "holdout_v0.2_freeze_record.json"
PROTOCOL_METADATA_PATH = _CASES_DIR / "protocol_v0.2_metadata.json"
PROTOCOL_DOC_PATH = _REPO_ROOT / "docs" / "evaluator_diagnostic_protocol_v0.2.md"
DEVELOPMENT_DATASET_PATH = _CASES_DIR / "diagnostic_pairs_v0.1.jsonl"

# Frozen SHA-256 of the confirmatory holdout dataset v0.2 (must match at runtime).
CONFIRMATORY_DATASET_SHA256 = (
    "f14e2a87c7a62345963d389441388c4f74a91b9b5bb00457ed580da285420569"
)
# Frozen SHA-256 of the development dataset v0.1 (retrospective only).
DEVELOPMENT_DATASET_SHA256 = (
    "a004715338c97d9e85b92fe0221a18631aa2884f6bb8b1d78a66066ccdd12664"
)

# Frozen judge condition (Protocol v0.2 Section 23). No moving alias, no model
# substitution, no retry, no self-repair.
FROZEN_JUDGE_PROVIDER = "openrouter"
FROZEN_JUDGE_MODEL_REQUESTED = "qwen/qwen3.5-plus-20260420"
FROZEN_JUDGE_BASE_URL = "https://openrouter.ai/api/v1"
FROZEN_TEMPERATURE = 0.0
FROZEN_STRUCTURED_OUTPUT_ENABLED = False
FROZEN_RETRY_ENABLED = False
FROZEN_SELF_REPAIR_ENABLED = False

# Experiment shape.
PAIR_COUNT = 24
REPEATS = 3
EXPECTED_CALLS = PAIR_COUNT * 2 * REPEATS  # 144
THEORETICAL_SCORE_SERIES = PAIR_COUNT * 2 * len(DIMENSION_IDS)  # 288
MIN_SUCCESSFUL_REPEATS = 2

# Frozen acceptance thresholds (Section 22).
PRIMARY_DIRECTIONAL_ACCURACY_THRESHOLD = 0.85
MEAN_PRIMARY_DROP_THRESHOLD = 1.0
PROTECTED_MAE_THRESHOLD = 0.5
WITHIN_ONE_REPEATABILITY_THRESHOLD = 0.95
SEMANTIC_COVERAGE_THRESHOLD = 0.90
PER_FAMILY_MIN_ELIGIBLE = 2


# ---------------------------------------------------------------------------
# Data types.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FamilyPartition:
    """One family's frozen primary / collateral / protected dimension partition."""

    family: str
    primary: tuple[str, ...]
    collateral: tuple[str, ...]
    protected: tuple[str, ...]


@dataclass(frozen=True)
class ConfirmatoryRecord:
    """One confirmatory evaluation at one (pair, variant, repeat).

    ``scores`` is ``None`` when the evaluation did NOT produce a successful
    semantic artifact (a UniversalEvaluationArtifact with ``structural_valid``
    true). ``failure_type`` then records the operational failure (either a
    frozen evaluator failure type or ``"gate_<stage>"`` for a Layer-0 gate
    failure). A failure is NEVER converted into a semantic score of zero.
    """

    pair_id: str
    variant: str  # "reference" | "degraded"
    repeat_index: int  # 1-based; frozen Protocol v0.2 uses repeats 1, 2, 3
    scores: dict[str, int] | None
    critical_flags: tuple[str, ...] = ()
    failure_type: str | None = None


@dataclass(frozen=True)
class IntegrityReport:
    """Dataset-integrity verification result (fail-fast before any Judge call)."""

    dataset_sha_match: bool
    pair_count_match: bool
    family_distribution_match: bool
    freeze_status_frozen: bool
    messages: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            self.dataset_sha_match
            and self.pair_count_match
            and self.family_distribution_match
            and self.freeze_status_frozen
        )


@dataclass(frozen=True)
class PrimaryDirectionalAccuracy:
    numerator: int
    denominator: int
    accuracy: float

    @property
    def passed(self) -> bool:
        return self.denominator > 0 and self.accuracy >= PRIMARY_DIRECTIONAL_ACCURACY_THRESHOLD


@dataclass(frozen=True)
class MeanPrimaryTargetedDrop:
    n: int
    mean_drop: float
    n_at_least_one: int = 0

    @property
    def passed(self) -> bool:
        return self.n > 0 and self.mean_drop >= MEAN_PRIMARY_DROP_THRESHOLD

    @property
    def proportion_at_least_one(self) -> float:
        return round(self.n_at_least_one / self.n, 4) if self.n else 0.0


@dataclass(frozen=True)
class ProtectedDimensionMAE:
    n_comparisons: int
    mae: float
    exact_zero_count: int = 0

    @property
    def passed(self) -> bool:
        return self.n_comparisons > 0 and self.mae <= PROTECTED_MAE_THRESHOLD

    @property
    def exact_zero_proportion(self) -> float:
        return round(self.exact_zero_count / self.n_comparisons, 4) if self.n_comparisons else 0.0


@dataclass(frozen=True)
class CollateralDiagnostics:
    n: int
    global_mean_signed: float
    global_mean_absolute: float
    per_dimension: dict[str, dict]
    per_family: dict[str, dict]


@dataclass(frozen=True)
class ConfirmatoryRepeatability:
    n_comparisons: int
    exact_agreement: float
    within_one_agreement: float
    eligible_series: int = 0

    @property
    def passed(self) -> bool:
        return (
            self.n_comparisons > 0
            and self.within_one_agreement >= WITHIN_ONE_REPEATABILITY_THRESHOLD
        )


@dataclass(frozen=True)
class SemanticCoverage:
    eligible: int
    total: int
    coverage: float
    per_family: dict[str, dict]

    @property
    def passed(self) -> bool:
        return self.total > 0 and self.coverage >= SEMANTIC_COVERAGE_THRESHOLD


@dataclass(frozen=True)
class ConfirmatoryFlagDiagnostics:
    tp: int
    fn: int
    fp: int
    per_flag: dict[str, dict]
    per_pair: dict[str, dict]
    reference_side_flags: tuple[dict, ...]


@dataclass(frozen=True)
class OperationalReliability:
    expected_calls: int
    successful: int
    failed: int
    success_rate: float
    failure_counts: dict[str, int]


@dataclass(frozen=True)
class SemanticValidationResult:
    primary_directional_accuracy: PrimaryDirectionalAccuracy
    mean_primary_targeted_drop: MeanPrimaryTargetedDrop
    protected_dimension_mae: ProtectedDimensionMAE
    repeatability: ConfirmatoryRepeatability
    semantic_pair_coverage: SemanticCoverage
    per_family_coverage_pass: bool
    overall: bool

    @property
    def verdict(self) -> str:
        return "PASS" if self.overall else "FAIL"


# ---------------------------------------------------------------------------
# Metadata loading + partition lookup.
# ---------------------------------------------------------------------------
def load_protocol_metadata(path: Path | None = None) -> dict:
    """Load the frozen v0.2 coupling-matrix metadata (Section 9/10)."""
    path = path or PROTOCOL_METADATA_PATH
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def family_partition(metadata: dict, family: str) -> FamilyPartition:
    """Return the frozen primary/collateral/protected partition for *family*."""
    entry = metadata["families"][family]
    return FamilyPartition(
        family=family,
        primary=tuple(entry["primary_target_dimensions"]),
        collateral=tuple(entry["allowed_collateral_dimensions"]),
        protected=tuple(entry["protected_dimensions"]),
    )


def load_freeze_record(path: Path | None = None) -> dict:
    path = path or FREEZE_RECORD_PATH
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Dataset integrity (fail-fast).
# ---------------------------------------------------------------------------
def verify_dataset_integrity(
    dataset_path: Path | None = None,
    *,
    freeze_record_path: Path | None = None,
    expected_sha: str = CONFIRMATORY_DATASET_SHA256,
    expected_pairs: int = PAIR_COUNT,
) -> IntegrityReport:
    """Verify the frozen holdout dataset integrity before any Judge call.

    Checks (all mandatory): dataset SHA-256 matches the frozen value; exactly
    ``expected_pairs`` pairs; 8 families x 3 pairs; freeze record status is
    ``Frozen`` and its recorded SHA matches. Returns an :class:`IntegrityReport`
    (never raises on a mismatch — the caller decides to fail fast).
    """
    dataset_path = dataset_path or CONFIRMATORY_DATASET_PATH
    freeze_record_path = freeze_record_path or FREEZE_RECORD_PATH
    messages: list[str] = []

    sha = _sha256_file(dataset_path)
    sha_match = sha == expected_sha
    if not sha_match:
        messages.append(
            f"dataset SHA mismatch: computed {sha}, expected {expected_sha}"
        )

    pairs = load_diagnostic_pairs(dataset_path)
    pair_count_match = len(pairs) == expected_pairs
    if not pair_count_match:
        messages.append(f"pair count mismatch: got {len(pairs)}, expected {expected_pairs}")

    family_counts = Counter(p.get("family") for p in pairs)
    family_distribution_match = (
        set(family_counts) == set(DIAGNOSTIC_FAMILIES)
        and all(n == 3 for n in family_counts.values())
    )
    if not family_distribution_match:
        messages.append(f"family distribution invalid: {dict(family_counts)}")

    freeze_status_frozen = False
    try:
        freeze = load_freeze_record(freeze_record_path)
        freeze_status_frozen = freeze.get("status") == "Frozen"
        if freeze.get("dataset_sha256") != expected_sha:
            messages.append(
                "freeze record dataset_sha256 does not match the frozen SHA"
            )
        if not freeze_status_frozen:
            messages.append(
                f"freeze record status is {freeze.get('status')!r}, expected 'Frozen'"
            )
    except FileNotFoundError:
        messages.append("freeze record not found")

    return IntegrityReport(
        dataset_sha_match=sha_match,
        pair_count_match=pair_count_match,
        family_distribution_match=family_distribution_match,
        freeze_status_frozen=freeze_status_frozen,
        messages=tuple(messages),
    )


# ---------------------------------------------------------------------------
# Eligibility + means.
# ---------------------------------------------------------------------------
def successful_repeat_count(
    records: Sequence[ConfirmatoryRecord], pair_id: str, variant: str
) -> int:
    return sum(
        1
        for r in records
        if r.pair_id == pair_id and r.variant == variant and r.scores is not None
    )


def _successful_records(
    records: Sequence[ConfirmatoryRecord], pair_id: str, variant: str
) -> list[ConfirmatoryRecord]:
    return [
        r
        for r in records
        if r.pair_id == pair_id and r.variant == variant and r.scores is not None
    ]


def variant_eligible(
    records: Sequence[ConfirmatoryRecord], pair_id: str, variant: str
) -> bool:
    return successful_repeat_count(records, pair_id, variant) >= MIN_SUCCESSFUL_REPEATS


def pair_eligible(records: Sequence[ConfirmatoryRecord], pair_id: str) -> bool:
    return variant_eligible(records, pair_id, "reference") and variant_eligible(
        records, pair_id, "degraded"
    )


def variant_mean_scores(
    records: Sequence[ConfirmatoryRecord], pair_id: str, variant: str
) -> dict[str, float] | None:
    """Arithmetic mean per dimension over successful repeats (Section 12.1)."""
    rs = _successful_records(records, pair_id, variant)
    if not rs:
        return None
    return {d: sum(r.scores[d] for r in rs) / len(rs) for d in DIMENSION_IDS}


# ---------------------------------------------------------------------------
# 1. Primary Directional Accuracy (Section 13).
# ---------------------------------------------------------------------------
def primary_directional_accuracy(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> PrimaryDirectionalAccuracy:
    numerator = 0
    denominator = 0
    for pair in pairs:
        pid = pair["pair_id"]
        if not pair_eligible(records, pid):
            continue
        part = family_partition(metadata, pair["family"])
        ref = variant_mean_scores(records, pid, "reference")
        deg = variant_mean_scores(records, pid, "degraded")
        for d in part.primary:
            denominator += 1
            if ref[d] > deg[d]:  # ties (delta == 0) do NOT count (Section 13)
                numerator += 1
    accuracy = round(numerator / denominator, 4) if denominator else 0.0
    return PrimaryDirectionalAccuracy(numerator, denominator, accuracy)


# ---------------------------------------------------------------------------
# 2. Mean Primary Targeted Drop (Section 14).
# ---------------------------------------------------------------------------
def mean_primary_targeted_drop(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> MeanPrimaryTargetedDrop:
    drops: list[float] = []
    for pair in pairs:
        pid = pair["pair_id"]
        if not pair_eligible(records, pid):
            continue
        part = family_partition(metadata, pair["family"])
        ref = variant_mean_scores(records, pid, "reference")
        deg = variant_mean_scores(records, pid, "degraded")
        for d in part.primary:
            drops.append(ref[d] - deg[d])
    mean = round(sum(drops) / len(drops), 4) if drops else 0.0
    n_at_least_one = sum(1 for x in drops if x >= 1.0)
    return MeanPrimaryTargetedDrop(len(drops), mean, n_at_least_one)


# ---------------------------------------------------------------------------
# 3. Protected-Dimension MAE (Section 15) — MICRO-average.
# ---------------------------------------------------------------------------
def protected_dimension_mae(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> ProtectedDimensionMAE:
    """Micro-average of ``abs(ref_mean - deg_mean)`` over every eligible
    (pair, protected-dimension) — NOT family-averaged, NOT weighted."""
    shifts: list[float] = []
    for pair in pairs:
        pid = pair["pair_id"]
        if not pair_eligible(records, pid):
            continue
        part = family_partition(metadata, pair["family"])
        ref = variant_mean_scores(records, pid, "reference")
        deg = variant_mean_scores(records, pid, "degraded")
        for d in part.protected:
            shifts.append(abs(ref[d] - deg[d]))
    mae = round(sum(shifts) / len(shifts), 4) if shifts else 0.0
    exact_zero = sum(1 for x in shifts if x == 0.0)
    return ProtectedDimensionMAE(len(shifts), mae, exact_zero)


# ---------------------------------------------------------------------------
# 4. Allowed-collateral diagnostics (Section 16) — descriptive only.
# ---------------------------------------------------------------------------
def collateral_diagnostics(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> CollateralDiagnostics:
    entries: list[tuple[str, str, float]] = []  # (family, dim, signed drop)
    for pair in pairs:
        pid = pair["pair_id"]
        if not pair_eligible(records, pid):
            continue
        part = family_partition(metadata, pair["family"])
        ref = variant_mean_scores(records, pid, "reference")
        deg = variant_mean_scores(records, pid, "degraded")
        for d in part.collateral:
            entries.append((pair["family"], d, ref[d] - deg[d]))

    signed = [e[2] for e in entries]
    absolute = [abs(x) for x in signed]
    global_mean_signed = round(sum(signed) / len(signed), 4) if signed else 0.0
    global_mean_absolute = round(sum(absolute) / len(absolute), 4) if absolute else 0.0

    def _dim_stats(dim: str) -> dict:
        vals = [e[2] for e in entries if e[1] == dim]
        return {
            "signed": round(sum(vals) / len(vals), 4) if vals else 0.0,
            "absolute": round(sum(abs(v) for v in vals) / len(vals), 4) if vals else 0.0,
            "n": len(vals),
        }

    def _family_stats(fam: str) -> dict:
        vals = [e[2] for e in entries if e[0] == fam]
        return {
            "signed": round(sum(vals) / len(vals), 4) if vals else 0.0,
            "absolute": round(sum(abs(v) for v in vals) / len(vals), 4) if vals else 0.0,
            "n": len(vals),
        }

    return CollateralDiagnostics(
        n=len(entries),
        global_mean_signed=global_mean_signed,
        global_mean_absolute=global_mean_absolute,
        per_dimension={d: _dim_stats(d) for d in DIMENSION_IDS},
        per_family={f: _family_stats(f) for f in DIAGNOSTIC_FAMILIES},
    )


# ---------------------------------------------------------------------------
# 5. Repeatability (Section 17) — per (pair, variant, dimension).
# ---------------------------------------------------------------------------
def confirmatory_repeatability(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
) -> ConfirmatoryRepeatability:
    n_comparisons = 0
    exact = 0
    within = 0
    eligible_series = 0
    for pair in pairs:
        pid = pair["pair_id"]
        for variant in ("reference", "degraded"):
            for d in DIMENSION_IDS:
                scores = [
                    r.scores[d] for r in _successful_records(records, pid, variant)
                ]
                if len(scores) < 2:
                    continue
                eligible_series += 1
                for a, b in combinations(scores, 2):
                    n_comparisons += 1
                    if a == b:
                        exact += 1
                    if abs(a - b) <= 1:
                        within += 1
    exact_rate = round(exact / n_comparisons, 4) if n_comparisons else 0.0
    within_rate = round(within / n_comparisons, 4) if n_comparisons else 0.0
    return ConfirmatoryRepeatability(n_comparisons, exact_rate, within_rate, eligible_series)


# ---------------------------------------------------------------------------
# 6. Semantic Pair Coverage (Section 18).
# ---------------------------------------------------------------------------
def semantic_pair_coverage(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
) -> SemanticCoverage:
    eligible = sum(1 for p in pairs if pair_eligible(records, p["pair_id"]))
    total = len(pairs)
    coverage = round(eligible / total, 4) if total else 0.0
    per_family: dict[str, dict] = {}
    for fam in DIAGNOSTIC_FAMILIES:
        fam_pairs = [p for p in pairs if p["family"] == fam]
        fam_eligible = sum(1 for p in fam_pairs if pair_eligible(records, p["pair_id"]))
        per_family[fam] = {"eligible": fam_eligible, "total": len(fam_pairs)}
    return SemanticCoverage(eligible, total, coverage, per_family)


# ---------------------------------------------------------------------------
# 7. Critical Flag Diagnostics (Section 19) — strict majority.
# ---------------------------------------------------------------------------
def confirmatory_flag_diagnostics(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
) -> ConfirmatoryFlagDiagnostics:
    tp = 0
    fn = 0
    fp = 0
    per_flag: dict[str, dict] = {f: {"tp": 0, "fn": 0, "fp": 0} for f in CRITICAL_FLAGS}
    per_pair: dict[str, dict] = {}
    reference_side: list[dict] = []

    for pair in pairs:
        pid = pair["pair_id"]
        expected = set(pair["expected_flags"])

        # Reference-side flags: always reported separately (never merged into FP).
        for r in _successful_records(records, pid, "reference"):
            for flag in r.critical_flags:
                reference_side.append({"pair_id": pid, "flag": flag})

        degraded_success = _successful_records(records, pid, "degraded")
        if len(degraded_success) < 2:
            # Excluded from pair-level flag-majority reporting (Section 19.2).
            per_pair[pid] = {"excluded": True, "successful_repeats": len(degraded_success)}
            continue

        pair_tp: list[str] = []
        pair_fn: list[str] = []
        pair_fp: list[str] = []
        for flag in CRITICAL_FLAGS:
            count = sum(1 for r in degraded_success if flag in r.critical_flags)
            detected = count * 2 > len(degraded_success)  # strictly > 50%
            if detected:
                if flag in expected:
                    tp += 1
                    per_flag[flag]["tp"] += 1
                    pair_tp.append(flag)
                else:
                    fp += 1
                    per_flag[flag]["fp"] += 1
                    pair_fp.append(flag)
            else:
                if flag in expected:
                    fn += 1
                    per_flag[flag]["fn"] += 1
                    pair_fn.append(flag)
        per_pair[pid] = {
            "excluded": False,
            "successful_repeats": len(degraded_success),
            "tp": pair_tp,
            "fn": pair_fn,
            "fp": pair_fp,
        }

    return ConfirmatoryFlagDiagnostics(
        tp=tp,
        fn=fn,
        fp=fp,
        per_flag=per_flag,
        per_pair=per_pair,
        reference_side_flags=tuple(reference_side),
    )


# ---------------------------------------------------------------------------
# 8. Operational reliability (Section 21) — descriptive only.
# ---------------------------------------------------------------------------
def operational_reliability(
    records: Sequence[ConfirmatoryRecord],
    expected_calls: int = EXPECTED_CALLS,
) -> OperationalReliability:
    successful = sum(1 for r in records if r.scores is not None)
    failed = len(records) - successful
    failure_counts = dict(
        Counter(r.failure_type for r in records if r.failure_type is not None)
    )
    rate = round(successful / expected_calls, 4) if expected_calls else 0.0
    return OperationalReliability(expected_calls, successful, failed, rate, failure_counts)


# ---------------------------------------------------------------------------
# 9. Semantic acceptance criteria (Section 22).
# ---------------------------------------------------------------------------
def evaluate_semantic_validation(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> SemanticValidationResult:
    pda = primary_directional_accuracy(records, pairs, metadata)
    mpd = mean_primary_targeted_drop(records, pairs, metadata)
    pmae = protected_dimension_mae(records, pairs, metadata)
    rep = confirmatory_repeatability(records, pairs)
    cov = semantic_pair_coverage(records, pairs)

    per_family_coverage_pass = all(
        cov.per_family[fam]["eligible"] >= PER_FAMILY_MIN_ELIGIBLE
        for fam in DIAGNOSTIC_FAMILIES
    )

    overall = all(
        [
            pda.passed,
            mpd.passed,
            pmae.passed,
            rep.passed,
            cov.passed,
            per_family_coverage_pass,
        ]
    )
    return SemanticValidationResult(
        primary_directional_accuracy=pda,
        mean_primary_targeted_drop=mpd,
        protected_dimension_mae=pmae,
        repeatability=rep,
        semantic_pair_coverage=cov,
        per_family_coverage_pass=per_family_coverage_pass,
        overall=overall,
    )


# ---------------------------------------------------------------------------
# Family-level reporting (Section 27).
# ---------------------------------------------------------------------------
def family_metrics(
    records: Sequence[ConfirmatoryRecord],
    pairs: Sequence[dict],
    metadata: dict,
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for fam in DIAGNOSTIC_FAMILIES:
        fam_pairs = [p for p in pairs if p["family"] == fam]
        pda = primary_directional_accuracy(records, fam_pairs, metadata)
        mpd = mean_primary_targeted_drop(records, fam_pairs, metadata)
        pmae = protected_dimension_mae(records, fam_pairs, metadata)
        col = collateral_diagnostics(records, fam_pairs, metadata)
        rep = confirmatory_repeatability(records, fam_pairs)
        flags = confirmatory_flag_diagnostics(records, fam_pairs)
        eligible = sum(1 for p in fam_pairs if pair_eligible(records, p["pair_id"]))
        out[fam] = {
            "total_pairs": len(fam_pairs),
            "eligible_pairs": eligible,
            "primary_directional_accuracy": {
                "numerator": pda.numerator,
                "denominator": pda.denominator,
                "accuracy": pda.accuracy,
            },
            "mean_primary_targeted_drop": mpd.mean_drop,
            "protected_dimension_mae": pmae.mae,
            "collateral_mean_signed_drop": col.global_mean_signed,
            "collateral_mean_absolute_shift": col.global_mean_absolute,
            "repeatability_within_one": rep.within_one_agreement,
            "critical_flags": {"tp": flags.tp, "fn": flags.fn, "fp": flags.fp},
        }
    return out
