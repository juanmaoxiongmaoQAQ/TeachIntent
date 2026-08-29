"""Offline tests for the Protocol v0.2 confirmatory metrics.

Verifies the frozen semantics in ``docs/evaluator_diagnostic_protocol_v0.2.md``:
variant/pair semantic eligibility, primary directional accuracy (strict > 0),
mean primary targeted drop, protected MAE (micro-average), collateral
diagnostics, per-dimension repeatability (all unordered pairs), semantic pair
coverage, strict-majority critical flags, operational reliability, and the
six-criterion Semantic Validation PASS/FAIL gate.

No API calls; synthetic records only.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_FAMILIES,
    ConfirmatoryRecord,
    collateral_diagnostics,
    confirmatory_flag_diagnostics,
    confirmatory_repeatability,
    evaluate_semantic_validation,
    family_metrics,
    family_partition,
    load_protocol_metadata,
    mean_primary_targeted_drop,
    operational_reliability,
    pair_eligible,
    primary_directional_accuracy,
    protected_dimension_mae,
    semantic_pair_coverage,
    successful_repeat_count,
    variant_eligible,
    variant_mean_scores,
)

D = DIMENSION_IDS


def _scores(**overrides) -> dict[str, int]:
    base = {d: 4 for d in D}
    base.update(overrides)
    return base


def _rec(pid, variant, repeat, scores=None, flags=(), failure=None):
    return ConfirmatoryRecord(
        pair_id=pid, variant=variant, repeat_index=repeat,
        scores=scores, critical_flags=tuple(flags), failure_type=failure,
    )


def _pair(pid, family, expected_flags=()):
    return {"pair_id": pid, "family": family, "expected_flags": list(expected_flags)}


def _meta(families: dict) -> dict:
    """Build a synthetic metadata dict from {family: (primary, collateral, protected)}."""
    return {
        "protocol_version": "v0.2",
        "families": {
            fam: {
                "primary_target_dimensions": list(p),
                "allowed_collateral_dimensions": list(c),
                "protected_dimensions": list(pr),
            }
            for fam, (p, c, pr) in families.items()
        },
    }


# Canonical family-A partition (D1 primary, D4 collateral).
A = (
    "intent_mismatch",
    ["pedagogical_intent_fidelity"],
    ["intent_specific_instructional_adequacy"],
    ["content_faithfulness_boundary", "learner_state_compatibility",
     "delivery_necessity_sparsity", "delivery_pedagogy_alignment"],
)
META_A = _meta({"intent_mismatch": (A[1], A[2], A[3])})


def _full_pairs() -> list[dict]:
    pairs = []
    for i, fam in enumerate(DIAGNOSTIC_FAMILIES):
        letter = "ABCDEFGH"[i]
        for j in range(3):
            pairs.append({"pair_id": f"HOLDOUT-{letter}-0{j+1}", "family": fam, "expected_flags": []})
    return pairs


def _perfect_records(pairs, metadata) -> list[ConfirmatoryRecord]:
    """Build 3 successful repeats per variant with a clean primary drop and
    zero protected shift, so every acceptance criterion passes."""
    records = []
    for p in pairs:
        part = family_partition(metadata, p["family"])
        for variant in ("reference", "degraded"):
            for repeat in range(1, 4):
                s = {}
                for d in D:
                    if d in part.primary:
                        s[d] = 4 if variant == "reference" else 1
                    elif d in part.collateral:
                        s[d] = 4 if variant == "reference" else 2
                    else:  # protected
                        s[d] = 4
                records.append(_rec(p["pair_id"], variant, repeat, s))
    return records


# ---------------------------------------------------------------------------
# 3. Family partition lookup (frozen coupling matrix).
# ---------------------------------------------------------------------------
def test_family_partition_lookup():
    md = load_protocol_metadata()
    a = family_partition(md, "intent_mismatch")
    assert a.primary == ("pedagogical_intent_fidelity",)
    assert a.collateral == ("intent_specific_instructional_adequacy",)
    assert "content_faithfulness_boundary" in a.protected

    g = family_partition(md, "delivery_pedagogy_conflict")
    assert g.primary == ("delivery_pedagogy_alignment",)
    assert set(g.collateral) == {"learner_state_compatibility", "delivery_necessity_sparsity"}

    e = family_partition(md, "incomplete_corrective_feedback")
    assert e.collateral == ()


# ---------------------------------------------------------------------------
# 5/6/7/8. Variant + pair eligibility.
# ---------------------------------------------------------------------------
def test_variant_eligible_3_of_3():
    recs = [_rec("P", "reference", 1, _scores()),
            _rec("P", "reference", 2, _scores()),
            _rec("P", "reference", 3, _scores())]
    assert variant_eligible(recs, "P", "reference") is True


def test_variant_eligible_2_of_3():
    recs = [_rec("P", "degraded", 1, _scores()),
            _rec("P", "degraded", 2, _scores()),
            _rec("P", "degraded", 3, None, failure="judge_api_error")]
    assert variant_eligible(recs, "P", "degraded") is True


def test_variant_ineligible_1_of_3():
    recs = [_rec("P", "degraded", 1, _scores()),
            _rec("P", "degraded", 2, None, failure="judge_api_error"),
            _rec("P", "degraded", 3, None, failure="judge_api_error")]
    assert variant_eligible(recs, "P", "degraded") is False
    assert successful_repeat_count(recs, "P", "degraded") == 1


def test_pair_eligible_requires_both_variants():
    # reference eligible (3/3), degraded ineligible (1/3).
    recs = [_rec("P", "reference", i, _scores()) for i in range(1, 4)]
    recs += [_rec("P", "degraded", 1, _scores()),
             _rec("P", "degraded", 2, None, failure="judge_api_error"),
             _rec("P", "degraded", 3, None, failure="judge_api_error")]
    assert variant_eligible(recs, "P", "reference") is True
    assert variant_eligible(recs, "P", "degraded") is False
    assert pair_eligible(recs, "P") is False


# ---------------------------------------------------------------------------
# 9/10/11/12. Primary directional accuracy.
# ---------------------------------------------------------------------------
def test_primary_directional_accuracy_basic():
    pairs = [_pair("P1", "intent_mismatch"), _pair("P2", "intent_mismatch")]
    recs = [
        _rec("P1", "reference", 1, _scores(pedagogical_intent_fidelity=4)),
        _rec("P1", "reference", 2, _scores(pedagogical_intent_fidelity=4)),
        _rec("P1", "degraded", 1, _scores(pedagogical_intent_fidelity=2)),
        _rec("P1", "degraded", 2, _scores(pedagogical_intent_fidelity=2)),
        _rec("P2", "reference", 1, _scores(pedagogical_intent_fidelity=4)),
        _rec("P2", "reference", 2, _scores(pedagogical_intent_fidelity=4)),
        _rec("P2", "degraded", 1, _scores(pedagogical_intent_fidelity=4)),  # tie
        _rec("P2", "degraded", 2, _scores(pedagogical_intent_fidelity=4)),
    ]
    r = primary_directional_accuracy(recs, pairs, META_A)
    assert r.numerator == 1
    assert r.denominator == 2
    assert r.accuracy == 0.5


def test_delta_zero_not_directional_success():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [
        _rec("P", "reference", 1, _scores(pedagogical_intent_fidelity=3)),
        _rec("P", "reference", 2, _scores(pedagogical_intent_fidelity=3)),
        _rec("P", "degraded", 1, _scores(pedagogical_intent_fidelity=3)),  # delta 0
        _rec("P", "degraded", 2, _scores(pedagogical_intent_fidelity=3)),
    ]
    r = primary_directional_accuracy(recs, pairs, META_A)
    assert r.numerator == 0
    assert r.denominator == 1


def test_negative_delta_not_success():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [
        _rec("P", "reference", 1, _scores(pedagogical_intent_fidelity=1)),
        _rec("P", "reference", 2, _scores(pedagogical_intent_fidelity=1)),
        _rec("P", "degraded", 1, _scores(pedagogical_intent_fidelity=4)),  # ref < deg
        _rec("P", "degraded", 2, _scores(pedagogical_intent_fidelity=4)),
    ]
    r = primary_directional_accuracy(recs, pairs, META_A)
    assert r.numerator == 0
    assert r.denominator == 1
    assert r.passed is False


# ---------------------------------------------------------------------------
# 13. Mean primary targeted drop.
# ---------------------------------------------------------------------------
def test_mean_primary_targeted_drop():
    pairs = [_pair("P1", "intent_mismatch"), _pair("P2", "intent_mismatch")]
    recs = [
        _rec("P1", "reference", 1, _scores(pedagogical_intent_fidelity=4)),
        _rec("P1", "reference", 2, _scores(pedagogical_intent_fidelity=4)),
        _rec("P1", "degraded", 1, _scores(pedagogical_intent_fidelity=1)),  # drop 3
        _rec("P1", "degraded", 2, _scores(pedagogical_intent_fidelity=1)),
        _rec("P2", "reference", 1, _scores(pedagogical_intent_fidelity=3)),
        _rec("P2", "reference", 2, _scores(pedagogical_intent_fidelity=3)),
        _rec("P2", "degraded", 1, _scores(pedagogical_intent_fidelity=2)),  # drop 1
        _rec("P2", "degraded", 2, _scores(pedagogical_intent_fidelity=2)),
    ]
    r = mean_primary_targeted_drop(recs, pairs, META_A)
    assert r.n == 2
    assert r.mean_drop == 2.0
    assert r.n_at_least_one == 2
    assert r.passed is True


# ---------------------------------------------------------------------------
# 14/15. Protected-Dimension MAE (micro-average).
# ---------------------------------------------------------------------------
def test_protected_mae_is_micro_average_not_family_average():
    # 2 families with different eligible pair counts; micro != family-average.
    meta = _meta({
        "fa": (["pedagogical_intent_fidelity"], [],
               ["content_faithfulness_boundary"]),
        "fb": (["learner_state_compatibility"], [],
               ["intent_specific_instructional_adequacy"]),
    })
    pairs = [_pair("PA", "fa"), _pair("PB1", "fb"), _pair("PB2", "fb")]
    recs = []
    # PA: protected shift = 2 (ref D2=4, deg D2=2)
    for _ in range(2):
        recs.append(_rec("PA", "reference", 1, _scores(content_faithfulness_boundary=4)))
        recs.append(_rec("PA", "degraded", 1, _scores(content_faithfulness_boundary=2)))
    # PB1/PB2: protected shift = 0
    for pid in ("PB1", "PB2"):
        for _ in range(2):
            recs.append(_rec(pid, "reference", 1, _scores(intent_specific_instructional_adequacy=4)))
            recs.append(_rec(pid, "degraded", 1, _scores(intent_specific_instructional_adequacy=4)))
    r = protected_dimension_mae(recs, pairs, meta)
    # micro = (2 + 0 + 0) / 3 = 0.6667; family-average would be (2 + 0)/2 = 1.0.
    assert r.n_comparisons == 3
    assert r.mae == pytest.approx(2 / 3, abs=1e-3)
    assert r.mae != 1.0
    assert r.exact_zero_count == 2


def test_collateral_not_in_protected_mae():
    meta = _meta({
        "fa": (["pedagogical_intent_fidelity"],
               ["intent_specific_instructional_adequacy"],
               ["content_faithfulness_boundary"]),
    })
    pairs = [_pair("P", "fa")]
    recs = [
        _rec("P", "reference", 1, _scores(pedagogical_intent_fidelity=4,
                                          intent_specific_instructional_adequacy=4,
                                          content_faithfulness_boundary=4)),
        _rec("P", "reference", 2, _scores(pedagogical_intent_fidelity=4,
                                          intent_specific_instructional_adequacy=4,
                                          content_faithfulness_boundary=4)),
        # degraded: collateral D4 drops hard, protected D2 unchanged.
        _rec("P", "degraded", 1, _scores(pedagogical_intent_fidelity=1,
                                         intent_specific_instructional_adequacy=1,
                                         content_faithfulness_boundary=4)),
        _rec("P", "degraded", 2, _scores(pedagogical_intent_fidelity=1,
                                         intent_specific_instructional_adequacy=1,
                                         content_faithfulness_boundary=4)),
    ]
    r = protected_dimension_mae(recs, pairs, meta)
    assert r.n_comparisons == 1  # only the single protected dimension D2
    assert r.mae == 0.0  # collateral D4 shift is excluded


def test_collateral_diagnostics_reports_shifts():
    meta = _meta({
        "fa": (["pedagogical_intent_fidelity"],
               ["intent_specific_instructional_adequacy"],
               ["content_faithfulness_boundary"]),
    })
    pairs = [_pair("P", "fa")]
    recs = [
        _rec("P", "reference", 1, _scores(intent_specific_instructional_adequacy=4)),
        _rec("P", "reference", 2, _scores(intent_specific_instructional_adequacy=4)),
        _rec("P", "degraded", 1, _scores(intent_specific_instructional_adequacy=1)),
        _rec("P", "degraded", 2, _scores(intent_specific_instructional_adequacy=1)),
    ]
    r = collateral_diagnostics(recs, pairs, meta)
    assert r.n == 1
    assert r.global_mean_signed == 3.0
    assert r.global_mean_absolute == 3.0
    assert r.per_dimension["intent_specific_instructional_adequacy"]["signed"] == 3.0


# ---------------------------------------------------------------------------
# 16/17/18/19. Repeatability (per dimension).
# ---------------------------------------------------------------------------
def test_repeatability_3_repeats_3_unordered_pairs():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [_rec("P", "reference", i, _scores()) for i in range(1, 4)]
    r = confirmatory_repeatability(recs, pairs)
    # 6 dimensions x C(3,2)=3 unordered pairs = 18 comparisons.
    assert r.n_comparisons == 18
    assert r.eligible_series == 6


def test_repeatability_2_repeats_1_unordered_pair():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [_rec("P", "reference", i, _scores()) for i in range(2)]
    r = confirmatory_repeatability(recs, pairs)
    # 6 dimensions x C(2,2)=1 = 6 comparisons.
    assert r.n_comparisons == 6


def test_repeatability_exact_and_within_one():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [
        _rec("P", "reference", 1, _scores(pedagogical_intent_fidelity=4)),
        _rec("P", "reference", 2, _scores(pedagogical_intent_fidelity=4)),
        _rec("P", "reference", 3, _scores(pedagogical_intent_fidelity=3)),
    ]
    r = confirmatory_repeatability(recs, pairs)
    # D1 pairs: (4,4) exact, (4,3) within, (4,3) within -> 1 exact, 3 within
    # D2-D6: 3 exact each (5 dims). total exact = 1 + 15 = 16; within = 18.
    assert r.n_comparisons == 18
    assert r.exact_agreement == pytest.approx(16 / 18, abs=1e-4)
    assert r.within_one_agreement == 1.0


def test_repeatability_outside_one():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [
        _rec("P", "reference", 1, _scores(pedagogical_intent_fidelity=4)),
        _rec("P", "reference", 2, _scores(pedagogical_intent_fidelity=2)),  # diff 2
    ]
    r = confirmatory_repeatability(recs, pairs)
    # D1 (4,2) not within-one; D2-D6 exact. 6 comparisons; within = 5.
    assert r.n_comparisons == 6
    assert r.exact_agreement == pytest.approx(5 / 6, abs=1e-4)
    assert r.within_one_agreement == pytest.approx(5 / 6, abs=1e-4)
    assert r.passed is False


# ---------------------------------------------------------------------------
# 20/21/22. Semantic pair coverage.
# ---------------------------------------------------------------------------
def test_semantic_coverage_22_of_24_pass():
    pairs = _full_pairs()
    eligible = {p["pair_id"] for p in pairs
                if p["pair_id"] not in {"HOLDOUT-A-01", "HOLDOUT-B-01"}}
    recs = []
    for p in pairs:
        if p["pair_id"] in eligible:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "reference", 2, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 2, _scores())]
        else:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores())]
    cov = semantic_pair_coverage(recs, pairs)
    assert cov.eligible == 22
    assert cov.total == 24
    assert cov.coverage == pytest.approx(22 / 24, abs=1e-4)
    assert cov.passed is True


def test_semantic_coverage_21_of_24_fail():
    pairs = _full_pairs()
    ineligible = {"HOLDOUT-A-01", "HOLDOUT-B-01", "HOLDOUT-C-01"}
    recs = []
    for p in pairs:
        if p["pair_id"] in ineligible:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores())]
        else:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "reference", 2, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 2, _scores())]
    cov = semantic_pair_coverage(recs, pairs)
    assert cov.eligible == 21
    assert cov.coverage == pytest.approx(21 / 24, abs=1e-4)
    assert cov.passed is False


def test_family_1_of_3_causes_overall_fail():
    pairs = _full_pairs()
    # Family H (prompt_injection_compliance) has only 1 eligible pair.
    h_pairs = [p for p in pairs if p["family"] == "prompt_injection_compliance"]
    eligible = {p["pair_id"] for p in pairs if p["family"] != "prompt_injection_compliance"}
    eligible.add(h_pairs[0]["pair_id"])
    recs = []
    for p in pairs:
        if p["pair_id"] in eligible:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "reference", 2, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 2, _scores())]
        else:
            recs += [_rec(p["pair_id"], "reference", 1, _scores()),
                     _rec(p["pair_id"], "degraded", 1, _scores())]
    result = evaluate_semantic_validation(recs, pairs, load_protocol_metadata())
    # global coverage 22/24 >= 90%, but family H has 1/3 -> per-family fail.
    assert result.semantic_pair_coverage.coverage >= 0.90
    assert result.per_family_coverage_pass is False
    assert result.overall is False


# ---------------------------------------------------------------------------
# 23/24/25/26/27. Critical flag majority.
# ---------------------------------------------------------------------------
def test_flag_expected_2_of_3_is_tp():
    pairs = [_pair("P", "content_contradiction", ["content_anchor_contradiction"])]
    recs = [_rec("P", "degraded", 1, _scores(), ["content_anchor_contradiction"]),
            _rec("P", "degraded", 2, _scores(), ["content_anchor_contradiction"]),
            _rec("P", "degraded", 3, _scores(), [])]
    d = confirmatory_flag_diagnostics(recs, pairs)
    assert d.tp == 1 and d.fn == 0 and d.fp == 0


def test_flag_expected_1_of_3_is_fn():
    pairs = [_pair("P", "content_contradiction", ["content_anchor_contradiction"])]
    recs = [_rec("P", "degraded", 1, _scores(), ["content_anchor_contradiction"]),
            _rec("P", "degraded", 2, _scores(), []),
            _rec("P", "degraded", 3, _scores(), [])]
    d = confirmatory_flag_diagnostics(recs, pairs)
    assert d.tp == 0 and d.fn == 1 and d.fp == 0


def test_flag_unexpected_2_of_3_is_fp():
    pairs = [_pair("P", "intent_mismatch", [])]
    recs = [_rec("P", "degraded", 1, _scores(), ["learner_humiliation"]),
            _rec("P", "degraded", 2, _scores(), ["learner_humiliation"]),
            _rec("P", "degraded", 3, _scores(), [])]
    d = confirmatory_flag_diagnostics(recs, pairs)
    assert d.tp == 0 and d.fn == 0 and d.fp == 1


def test_flag_one_successful_degraded_excluded():
    pairs = [_pair("P", "content_contradiction", ["content_anchor_contradiction"])]
    recs = [_rec("P", "degraded", 1, _scores(), ["content_anchor_contradiction"]),
            _rec("P", "degraded", 2, None, failure="judge_api_error"),
            _rec("P", "degraded", 3, None, failure="judge_api_error")]
    d = confirmatory_flag_diagnostics(recs, pairs)
    assert d.tp == 0 and d.fn == 0 and d.fp == 0
    assert d.per_pair["P"]["excluded"] is True


def test_reference_flags_separate_from_fp():
    pairs = [_pair("P", "intent_mismatch", [])]
    recs = [_rec("P", "degraded", 1, _scores(), []),
            _rec("P", "degraded", 2, _scores(), []),
            _rec("P", "reference", 1, _scores(), ["content_anchor_contradiction"]),
            _rec("P", "reference", 2, _scores(), ["content_anchor_contradiction"])]
    d = confirmatory_flag_diagnostics(recs, pairs)
    assert d.fp == 0  # reference flags must not be merged into degraded FP
    assert len(d.reference_side_flags) == 2
    assert all(f["flag"] == "content_anchor_contradiction" for f in d.reference_side_flags)


# ---------------------------------------------------------------------------
# 28/29. Failures not zeros; operational reliability descriptive.
# ---------------------------------------------------------------------------
def test_failure_not_converted_to_semantic_zero():
    pairs = [_pair("P", "intent_mismatch")]
    recs = [_rec("P", "degraded", 1, None, failure="judge_api_error"),
            _rec("P", "degraded", 2, None, failure="judge_api_error")]
    assert variant_eligible(recs, "P", "degraded") is False
    assert variant_mean_scores(recs, "P", "degraded") is None  # no zero injected
    op = operational_reliability(recs, 144)
    assert op.successful == 0
    assert op.failed == 2
    assert op.failure_counts == {"judge_api_error": 2}


def test_operational_reliability_descriptive_only():
    recs = [_rec("P", "reference", 1, _scores())]
    op = operational_reliability(recs, 144)
    assert op.expected_calls == 144
    assert op.successful == 1
    assert op.success_rate == pytest.approx(1 / 144, abs=1e-4)
    # No hard PASS/FAIL threshold exists on operational reliability.
    assert not hasattr(op, "passed")


# ---------------------------------------------------------------------------
# 30/31. Semantic validation PASS / FAIL.
# ---------------------------------------------------------------------------
def test_all_six_criteria_pass_gives_pass():
    pairs = _full_pairs()
    md = load_protocol_metadata()
    recs = _perfect_records(pairs, md)
    result = evaluate_semantic_validation(recs, pairs, md)
    assert result.primary_directional_accuracy.passed is True
    assert result.mean_primary_targeted_drop.passed is True
    assert result.protected_dimension_mae.passed is True
    assert result.repeatability.passed is True
    assert result.semantic_pair_coverage.passed is True
    assert result.per_family_coverage_pass is True
    assert result.overall is True
    assert result.verdict == "PASS"


def test_any_one_criterion_fail_gives_fail():
    pairs = _full_pairs()
    md = load_protocol_metadata()
    base = _perfect_records(pairs, md)
    fam = {p["pair_id"]: p["family"] for p in pairs}

    def corrupt_protected_mae(recs):
        out = []
        for r in recs:
            if r.variant == "degraded":
                part = family_partition(md, fam[r.pair_id])
                s = dict(r.scores)
                for d in part.protected:
                    s[d] = 3  # shift every protected dim by 1 -> MAE = 1.0
                out.append(replace(r, scores=s))
            else:
                out.append(r)
        return out

    def corrupt_directional(recs):
        # Tie every primary comparison -> directional accuracy = 0%.
        out = []
        for r in recs:
            if r.variant == "degraded":
                part = family_partition(md, fam[r.pair_id])
                s = dict(r.scores)
                for d in part.primary:
                    s[d] = 4  # degraded primary == reference primary
                out.append(replace(r, scores=s))
            else:
                out.append(r)
        return out

    def corrupt_mean_drop(recs):
        # Zero every primary drop -> mean drop = 0 (< 1.0).
        out = []
        for r in recs:
            part = family_partition(md, fam[r.pair_id])
            s = dict(r.scores)
            for d in part.primary:
                s[d] = 2  # same for reference and degraded
            out.append(replace(r, scores=s))
        return out

    def corrupt_repeatability(recs):
        # One degraded repeat diverges by > 1 in every dim.
        out = []
        for r in recs:
            if r.variant == "degraded" and r.repeat_index == 3:
                out.append(replace(r, scores={d: 0 for d in D}))
            else:
                out.append(r)
        return out

    def corrupt_family_coverage(recs):
        # Drop one family to 1/3 eligible (drop 2 pairs' successful repeats).
        h_pairs = [p for p in pairs if p["family"] == "prompt_injection_compliance"]
        drop_ids = {h_pairs[1]["pair_id"], h_pairs[2]["pair_id"]}
        out = []
        for r in recs:
            if r.pair_id in drop_ids and r.repeat_index >= 2:
                out.append(replace(r, scores=None, failure_type="judge_api_error"))
            else:
                out.append(r)
        return out

    # Protected MAE fail (single criterion).
    r1 = evaluate_semantic_validation(corrupt_protected_mae(base), pairs, md)
    assert r1.protected_dimension_mae.passed is False
    assert r1.primary_directional_accuracy.passed is True
    assert r1.overall is False

    # Directional accuracy fail.
    r2 = evaluate_semantic_validation(corrupt_directional(base), pairs, md)
    assert r2.primary_directional_accuracy.passed is False
    assert r2.overall is False

    # Mean targeted drop fail.
    r3 = evaluate_semantic_validation(corrupt_mean_drop(base), pairs, md)
    assert r3.mean_primary_targeted_drop.passed is False
    assert r3.overall is False

    # Repeatability fail.
    r4 = evaluate_semantic_validation(corrupt_repeatability(base), pairs, md)
    assert r4.repeatability.passed is False
    assert r4.overall is False

    # Per-family coverage fail (global coverage still >= 90%).
    r5 = evaluate_semantic_validation(corrupt_family_coverage(base), pairs, md)
    assert r5.semantic_pair_coverage.coverage >= 0.90
    assert r5.per_family_coverage_pass is False
    assert r5.overall is False


# ---------------------------------------------------------------------------
# Family metrics.
# ---------------------------------------------------------------------------
def test_family_metrics_covers_all_8_families():
    pairs = _full_pairs()
    md = load_protocol_metadata()
    recs = _perfect_records(pairs, md)
    fm = family_metrics(recs, pairs, md)
    assert set(fm.keys()) == set(DIAGNOSTIC_FAMILIES)
    for fam in DIAGNOSTIC_FAMILIES:
        assert fm[fam]["total_pairs"] == 3
        assert fm[fam]["eligible_pairs"] == 3
        assert fm[fam]["primary_directional_accuracy"]["denominator"] == 3
