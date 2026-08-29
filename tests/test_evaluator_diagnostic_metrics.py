"""Tests for the diagnostic metrics calculator.

All offline; uses synthetic EvaluationRecords to exercise each metric,
including zero-denominator / error handling.
"""

from __future__ import annotations

import pytest

from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.evaluator_diagnostic import (
    EvaluationRecord,
    critical_flag_diagnostics,
    directional_accuracy,
    mean_targeted_drop,
    off_target_mae,
    repeatability,
)

D = DIMENSION_IDS


def _scores(**overrides) -> dict[str, int]:
    base = {d: 4 for d in D}
    base.update(overrides)
    return base


def _rec(pair_id, side, repeat, scores, flags=(), failure=None):
    return EvaluationRecord(
        pair_id=pair_id, side=side, repeat_index=repeat,
        scores=scores, critical_flags=tuple(flags), failure_type=failure,
    )


def _pair(pair_id, target_dims, expected_flags=()):
    return {
        "pair_id": pair_id,
        "target_dimensions": list(target_dims),
        "expected_flags": list(expected_flags),
    }


# ---------------------------------------------------------------------------
# Directional accuracy.
# ---------------------------------------------------------------------------


def test_directional_accuracy_basic():
    pairs = [
        _pair("DIAG-A-01", ["pedagogical_intent_fidelity"]),
        _pair("DIAG-A-02", ["pedagogical_intent_fidelity"]),
    ]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "degraded", 0, _scores(pedagogical_intent_fidelity=2)),
        _rec("DIAG-A-02", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-02", "degraded", 0, _scores(pedagogical_intent_fidelity=4)),  # wrong direction
    ]
    result = directional_accuracy(records, pairs)
    assert result.numerator == 1
    assert result.denominator == 2
    assert result.accuracy == 0.5


def test_directional_accuracy_perfect():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "degraded", 0, _scores(pedagogical_intent_fidelity=1)),
    ]
    result = directional_accuracy(records, pairs)
    assert (result.numerator, result.denominator, result.accuracy) == (1, 1, 1.0)


def test_directional_accuracy_zero_denominator():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = []  # no records at all
    result = directional_accuracy(records, pairs)
    assert result.denominator == 0
    assert result.accuracy == 0.0
    assert result.skipped == 1


def test_directional_accuracy_skips_missing_scores():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [
        _rec("DIAG-A-01", "reference", 0, None, failure="judge_api_error"),
        _rec("DIAG-A-01", "degraded", 0, _scores(pedagogical_intent_fidelity=2)),
    ]
    result = directional_accuracy(records, pairs)
    assert result.denominator == 0
    assert result.skipped == 1


# ---------------------------------------------------------------------------
# Mean targeted drop.
# ---------------------------------------------------------------------------


def test_mean_targeted_drop():
    pairs = [
        _pair("DIAG-A-01", ["pedagogical_intent_fidelity"]),
        _pair("DIAG-B-01", ["content_faithfulness_boundary"]),
    ]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "degraded", 0, _scores(pedagogical_intent_fidelity=1)),  # drop 3
        _rec("DIAG-B-01", "reference", 0, _scores(content_faithfulness_boundary=3)),
        _rec("DIAG-B-01", "degraded", 0, _scores(content_faithfulness_boundary=2)),  # drop 1
    ]
    result = mean_targeted_drop(records, pairs)
    assert result.n == 2
    assert result.mean_drop == 2.0  # (3 + 1) / 2


def test_mean_targeted_drop_zero_denominator():
    result = mean_targeted_drop([], [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])])
    assert result.n == 0
    assert result.mean_drop == 0.0


# ---------------------------------------------------------------------------
# Off-target MAE.
# ---------------------------------------------------------------------------


def test_off_target_mae():
    # 6 dims; target is D1. Off-target = the other 5 dims.
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    ref = _scores(pedagogical_intent_fidelity=4)
    # All off-target dims drop by 1 -> MAE = 1.0
    deg = {d: (3 if d != "pedagogical_intent_fidelity" else 2) for d in D}
    records = [
        _rec("DIAG-A-01", "reference", 0, ref),
        _rec("DIAG-A-01", "degraded", 0, deg),
    ]
    result = off_target_mae(records, pairs)
    assert result.n == 5
    assert result.mae == 1.0


def test_off_target_mae_zero():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "degraded", 0, _scores(pedagogical_intent_fidelity=1)),
    ]
    result = off_target_mae(records, pairs)
    assert result.mae == 0.0


def test_off_target_mae_zero_denominator():
    result = off_target_mae([], [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])])
    assert result.n == 0
    assert result.mae == 0.0


# ---------------------------------------------------------------------------
# Repeatability.
# ---------------------------------------------------------------------------


def test_repeatability_exact_and_within_one():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "reference", 1, _scores(pedagogical_intent_fidelity=4)),  # exact
        _rec("DIAG-A-01", "reference", 2, _scores(pedagogical_intent_fidelity=3)),  # within 1
    ]
    result = repeatability(records, pairs)
    assert result.n_pairs == 3  # 3 unordered pairs
    # exact: (0,1); within: (0,1),(0,2),(1,2) all within one
    assert result.exact_agreement == pytest.approx(1 / 3, abs=1e-4)
    assert result.within_one_agreement == 1.0


def test_repeatability_outside_one():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4)),
        _rec("DIAG-A-01", "reference", 1, _scores(pedagogical_intent_fidelity=2)),  # diff 2
    ]
    result = repeatability(records, pairs)
    assert result.n_pairs == 1
    assert result.exact_agreement == 0.0
    assert result.within_one_agreement == 0.0


def test_repeatability_zero_denominator():
    result = repeatability([], [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])])
    assert result.n_pairs == 0
    assert result.within_one_agreement == 0.0


def test_repeatability_needs_two_runs():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"])]
    records = [_rec("DIAG-A-01", "reference", 0, _scores(pedagogical_intent_fidelity=4))]
    result = repeatability(records, pairs)
    assert result.n_pairs == 0


# ---------------------------------------------------------------------------
# Critical flag diagnostics.
# ---------------------------------------------------------------------------


def test_flag_tp_fn_fp():
    pairs = [
        _pair("DIAG-B-01", ["content_faithfulness_boundary"], ["content_anchor_contradiction"]),
        _pair("DIAG-A-01", ["pedagogical_intent_fidelity"], []),  # no expected flags
    ]
    records = [
        # B-01: expected flag raised in degraded -> TP
        _rec("DIAG-B-01", "degraded", 0, _scores(), ["content_anchor_contradiction"]),
        # A-01: no expected flags, but a flag raised -> FP
        _rec("DIAG-A-01", "degraded", 0, _scores(), ["learner_humiliation"]),
    ]
    result = critical_flag_diagnostics(records, pairs)
    assert result.tp == 1
    assert result.fn == 0
    assert result.fp == 1
    assert result.expected_flags == 1
    assert result.non_expected_cases == 1


def test_flag_fn():
    pairs = [
        _pair("DIAG-B-01", ["content_faithfulness_boundary"], ["content_anchor_contradiction"]),
    ]
    records = [
        _rec("DIAG-B-01", "degraded", 0, _scores(), []),  # flag NOT raised -> FN
    ]
    result = critical_flag_diagnostics(records, pairs)
    assert result.tp == 0
    assert result.fn == 1
    assert result.fp == 0


def test_flag_fp_from_reference_side():
    pairs = [_pair("DIAG-A-01", ["pedagogical_intent_fidelity"], [])]
    records = [
        _rec("DIAG-A-01", "reference", 0, _scores(), ["content_anchor_contradiction"]),
    ]
    result = critical_flag_diagnostics(records, pairs)
    assert result.fp == 1


def test_flag_union_across_repeats():
    # Flag raised in any repeat counts.
    pairs = [_pair("DIAG-B-01", ["content_faithfulness_boundary"], ["content_anchor_contradiction"])]
    records = [
        _rec("DIAG-B-01", "degraded", 0, _scores(), []),
        _rec("DIAG-B-01", "degraded", 1, _scores(), ["content_anchor_contradiction"]),
    ]
    result = critical_flag_diagnostics(records, pairs)
    assert result.tp == 1
    assert result.fn == 0


def test_flag_diagnostics_empty():
    result = critical_flag_diagnostics([], [])
    assert (result.tp, result.fn, result.fp) == (0, 0, 0)
