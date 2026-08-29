"""Diagnostic metrics for controlled perturbation validation.

Implements the frozen metrics from the evaluator validation plan:

1. **Directional Accuracy** — for each pair's target dimension,
   ``reference_score > degraded_score``. Acceptance ``>= 85%``. Reports
   numerator / denominator.
2. **Mean Targeted Drop** — mean of ``reference_score - degraded_score`` over
   target dimensions. Acceptance ``>= 1.0``.
3. **Off-target MAE** — mean of ``abs(reference_score - degraded_score)`` over
   non-target dimensions. Acceptance ``<= 0.5``.
4. **Repeatability** — over all unordered run pairs of the same plan, exact
   agreement and within-one-point agreement. Acceptance: within-one ``>= 95%``.
5. **Critical Flag diagnostics** — TP / FN for ``expected_flags`` and explicit
   FP for cases without expected flags. No fixed threshold; report only.

All functions are pure and deterministic; they never call the judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Sequence

from ..evaluator.rubric import DIMENSION_IDS

__all__ = [
    "DirectionalAccuracy",
    "MeanTargetedDrop",
    "OffTargetMAE",
    "Repeatability",
    "FlagDiagnostics",
    "EvaluationRecord",
    "directional_accuracy",
    "mean_targeted_drop",
    "off_target_mae",
    "repeatability",
    "critical_flag_diagnostics",
]


@dataclass(frozen=True)
class EvaluationRecord:
    """One evaluation result for one (pair, side) at one repeat.

    Attributes:
        pair_id: e.g. ``"DIAG-A-01"``.
        side: ``"reference"`` or ``"degraded"``.
        repeat_index: 0-based repeat number within the (pair, side).
        scores: dict dimension_id -> int score (0-4). ``None`` if the run did
            not produce a structurally valid artifact.
        critical_flags: tuple of raised critical-flag names.
        failure_type: evaluator failure type if the run failed, else ``None``.
    """

    pair_id: str
    side: str
    repeat_index: int
    scores: dict[str, int] | None
    critical_flags: tuple[str, ...] = ()
    failure_type: str | None = None


@dataclass(frozen=True)
class DirectionalAccuracy:
    numerator: int
    denominator: int
    accuracy: float
    skipped: int = 0

    @property
    def passed(self) -> bool:
        return self.denominator > 0 and self.accuracy >= 0.85


@dataclass(frozen=True)
class MeanTargetedDrop:
    n: int
    mean_drop: float
    skipped: int = 0

    @property
    def passed(self) -> bool:
        return self.n > 0 and self.mean_drop >= 1.0


@dataclass(frozen=True)
class OffTargetMAE:
    n: int
    mae: float
    skipped: int = 0

    @property
    def passed(self) -> bool:
        return self.n > 0 and self.mae <= 0.5


@dataclass(frozen=True)
class Repeatability:
    n_pairs: int
    exact_agreement: float
    within_one_agreement: float
    n_runs: int = 0

    @property
    def passed(self) -> bool:
        return self.n_pairs > 0 and self.within_one_agreement >= 0.95


@dataclass(frozen=True)
class FlagDiagnostics:
    tp: int
    fn: int
    fp: int
    expected_flags: int = 0
    non_expected_cases: int = 0
    # Per-pair detail for traceability.
    per_pair: dict[str, dict] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers: aggregate a (pair, side) across repeats.
# ---------------------------------------------------------------------------
def _mean_scores(
    records: Sequence[EvaluationRecord], pair_id: str, side: str
) -> dict[str, float] | None:
    """Mean score per dimension across all repeats for one (pair, side).

    Returns None if no structurally valid run exists for that (pair, side).
    """
    matching = [
        r for r in records if r.pair_id == pair_id and r.side == side
        and r.scores is not None
    ]
    if not matching:
        return None
    means: dict[str, float] = {}
    for dim in DIMENSION_IDS:
        means[dim] = sum(r.scores[dim] for r in matching) / len(matching)
    return means


def _union_flags(
    records: Sequence[EvaluationRecord], pair_id: str, side: str
) -> set[str]:
    """Union of raised flags across all repeats for one (pair, side)."""
    return {
        flag
        for r in records
        if r.pair_id == pair_id and r.side == side
        for flag in r.critical_flags
    }


# ---------------------------------------------------------------------------
# 1. Directional Accuracy.
# ---------------------------------------------------------------------------
def directional_accuracy(
    records: Sequence[EvaluationRecord],
    pairs: Sequence[dict],
) -> DirectionalAccuracy:
    """Directional accuracy over all targeted comparisons.

    For each pair, for each target dimension, compare mean reference score vs
    mean degraded score. A comparison is *correct* when
    ``reference > degraded``. Comparisons where either side has no valid score
    are counted in ``skipped`` and excluded from the denominator.
    """
    numerator = 0
    denominator = 0
    skipped = 0
    for pair in pairs:
        pid = pair["pair_id"]
        ref = _mean_scores(records, pid, "reference")
        deg = _mean_scores(records, pid, "degraded")
        if ref is None or deg is None:
            skipped += len(pair["target_dimensions"])
            continue
        for dim in pair["target_dimensions"]:
            if dim not in DIMENSION_IDS:
                continue  # validator rejects this upstream; defensive skip
            denominator += 1
            if ref[dim] > deg[dim]:
                numerator += 1
    accuracy = round(numerator / denominator, 4) if denominator else 0.0
    return DirectionalAccuracy(numerator, denominator, accuracy, skipped)


# ---------------------------------------------------------------------------
# 2. Mean Targeted Drop.
# ---------------------------------------------------------------------------
def mean_targeted_drop(
    records: Sequence[EvaluationRecord],
    pairs: Sequence[dict],
) -> MeanTargetedDrop:
    """Mean of ``reference - degraded`` over all target dimensions."""
    drops: list[float] = []
    skipped = 0
    for pair in pairs:
        pid = pair["pair_id"]
        ref = _mean_scores(records, pid, "reference")
        deg = _mean_scores(records, pid, "degraded")
        if ref is None or deg is None:
            skipped += len(pair["target_dimensions"])
            continue
        for dim in pair["target_dimensions"]:
            if dim not in DIMENSION_IDS:
                continue
            drops.append(ref[dim] - deg[dim])
    mean = round(sum(drops) / len(drops), 4) if drops else 0.0
    return MeanTargetedDrop(len(drops), mean, skipped)


# ---------------------------------------------------------------------------
# 3. Off-target MAE.
# ---------------------------------------------------------------------------
def off_target_mae(
    records: Sequence[EvaluationRecord],
    pairs: Sequence[dict],
) -> OffTargetMAE:
    """Mean abs(reference - degraded) over non-target dimensions."""
    errors: list[float] = []
    skipped = 0
    for pair in pairs:
        pid = pair["pair_id"]
        target = set(pair["target_dimensions"])
        ref = _mean_scores(records, pid, "reference")
        deg = _mean_scores(records, pid, "degraded")
        if ref is None or deg is None:
            skipped += 1
            continue
        for dim in DIMENSION_IDS:
            if dim in target:
                continue
            errors.append(abs(ref[dim] - deg[dim]))
    mae = round(sum(errors) / len(errors), 4) if errors else 0.0
    return OffTargetMAE(len(errors), mae, skipped)


# ---------------------------------------------------------------------------
# 4. Repeatability.
# ---------------------------------------------------------------------------
def repeatability(
    records: Sequence[EvaluationRecord],
    pairs: Sequence[dict],
) -> Repeatability:
    """Repeatability of a plan across repeated runs.

    For each (pair, side) with at least two valid runs, enumerate all unordered
    run pairs. A run pair is an *exact agreement* if all six dimension scores
    are identical; *within-one* if the max per-dimension difference is <= 1.
    """
    n_pairs = 0
    exact = 0
    within = 0
    n_runs = 0
    for pair in pairs:
        for side in ("reference", "degraded"):
            runs = [
                r for r in records
                if r.pair_id == pair["pair_id"] and r.side == side
                and r.scores is not None
            ]
            if len(runs) < 2:
                continue
            for a, b in combinations(runs, 2):
                n_pairs += 1
                n_runs += 1
                diffs = [
                    abs(a.scores[d] - b.scores[d]) for d in DIMENSION_IDS
                ]
                if max(diffs) == 0:
                    exact += 1
                if max(diffs) <= 1:
                    within += 1
    exact_agreement = round(exact / n_pairs, 4) if n_pairs else 0.0
    within_agreement = round(within / n_pairs, 4) if n_pairs else 0.0
    return Repeatability(n_pairs, exact_agreement, within_agreement, n_runs)


# ---------------------------------------------------------------------------
# 5. Critical Flag diagnostics.
# ---------------------------------------------------------------------------
def critical_flag_diagnostics(
    records: Sequence[EvaluationRecord],
    pairs: Sequence[dict],
) -> FlagDiagnostics:
    """TP / FN for expected flags; explicit FP for cases without expected flags.

    A flag is "raised" if it appears in any repeat of the degraded plan (or,
    for FP detection, in any repeat of either side). Expected flags that were
    raised are TP; expected flags never raised are FN; raised flags that were
    not expected are FP.
    """
    tp = 0
    fn = 0
    fp = 0
    expected_total = 0
    non_expected_cases = 0
    per_pair: dict[str, dict] = {}

    for pair in pairs:
        pid = pair["pair_id"]
        expected = set(pair["expected_flags"])
        expected_total += len(expected)

        degraded_raised = _union_flags(records, pid, "degraded")
        reference_raised = _union_flags(records, pid, "reference")
        all_raised = degraded_raised | reference_raised

        pair_tp = sorted(expected & degraded_raised)
        pair_fn = sorted(expected - degraded_raised)
        # explicit FP: flags raised (any side) that were NOT expected.
        pair_fp = sorted(all_raised - expected)

        tp += len(pair_tp)
        fn += len(pair_fn)
        fp += len(pair_fp)
        if not expected:
            non_expected_cases += 1

        per_pair[pid] = {
            "expected": sorted(expected),
            "degraded_raised": sorted(degraded_raised),
            "reference_raised": sorted(reference_raised),
            "tp": pair_tp,
            "fn": pair_fn,
            "fp": pair_fp,
        }

    return FlagDiagnostics(
        tp=tp, fn=fn, fp=fp,
        expected_flags=expected_total,
        non_expected_cases=non_expected_cases,
        per_pair=per_pair,
    )
