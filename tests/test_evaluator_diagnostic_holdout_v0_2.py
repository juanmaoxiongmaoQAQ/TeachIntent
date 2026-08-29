"""Tests for the Protocol v0.2 holdout dataset contract and validator.

All offline. Verifies: 24 holdout pairs, 8x3 family distribution, new
HOLDOUT-* pair IDs, uniqueness, Layer-0 validity, input validity, unknown-field
rejection, invalid expected flag, and separation from the v0.1 development
dataset (id space + content de-dup). No API calls, no Evaluator scoring.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from teachintent.evaluator_diagnostic import (
    HOLDOUT_DATASET_PATH,
    DIAGNOSTIC_FAMILIES,
    EXPECTED_PAIR_COUNT,
    PAIRS_PER_FAMILY,
    HOLDOUT_PAIR_FIELDS,
    HOLDOUT_PAIR_ID_RE,
    load_diagnostic_pairs,
    validate_holdout_dataset,
)
from teachintent.evaluator.rubric import CRITICAL_FLAGS


@pytest.fixture(scope="module")
def pairs() -> list[dict]:
    return load_diagnostic_pairs(HOLDOUT_DATASET_PATH)


@pytest.fixture(scope="module")
def report():
    return validate_holdout_dataset()


def _write(tmp_path: Path, pairs: list[dict]) -> Path:
    path = tmp_path / "pairs.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for p in pairs:
            handle.write(json.dumps(p, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Counts + distribution.
# ---------------------------------------------------------------------------


def test_exactly_24_holdout_pairs(pairs):
    assert len(pairs) == EXPECTED_PAIR_COUNT == 24


def test_exactly_8_families(pairs):
    assert {p["family"] for p in pairs} == set(DIAGNOSTIC_FAMILIES)


def test_3_pairs_per_family(pairs):
    from collections import Counter
    counts = Counter(p["family"] for p in pairs)
    assert set(counts) == set(DIAGNOSTIC_FAMILIES)
    assert all(n == PAIRS_PER_FAMILY for n in counts.values())


# ---------------------------------------------------------------------------
# Pair ID: new HOLDOUT-* format, unique, prefix<->family.
# ---------------------------------------------------------------------------


def test_holdout_pair_ids_use_holdout_prefix(pairs):
    for p in pairs:
        assert HOLDOUT_PAIR_ID_RE.match(p["pair_id"]), p["pair_id"]


def test_pair_ids_unique(pairs):
    ids = [p["pair_id"] for p in pairs]
    assert len(ids) == len(set(ids)) == 24


def test_pair_id_prefix_matches_family(pairs):
    from teachintent.evaluator_diagnostic.dataset import FAMILY_PAIR_ID_PREFIXES
    for p in pairs:
        letter = p["pair_id"][len("HOLDOUT-"):][0]
        assert FAMILY_PAIR_ID_PREFIXES[letter] == p["family"]


def test_no_diag_prefix_reused(pairs):
    for p in pairs:
        assert not p["pair_id"].startswith("DIAG-")


# ---------------------------------------------------------------------------
# Dataset validates cleanly.
# ---------------------------------------------------------------------------


def test_holdout_dataset_all_passed(report):
    assert report.all_passed
    assert report.parsed_count == 24
    assert report.input_pass_count == 24
    assert report.reference_pass_count == 24
    assert report.degraded_pass_count == 24
    assert not report.case_errors


def test_all_plans_layer0_valid(pairs):
    from teachintent.models import SpeechPlan
    from teachintent.validators import iter_speech_plan_errors
    for p in pairs:
        for key in ("reference_plan", "degraded_plan"):
            plan = p[key]
            assert not list(iter_speech_plan_errors(plan)), f"{p['pair_id']} {key}"
            SpeechPlan.model_validate(plan)


def test_all_inputs_valid(pairs):
    from teachintent.models import TeachIntentInput
    from teachintent.validators import iter_input_errors
    for p in pairs:
        assert not list(iter_input_errors(p["input"])), p["pair_id"]
        TeachIntentInput.model_validate(p["input"])


def test_reference_neq_degraded(pairs):
    for p in pairs:
        assert p["reference_plan"] != p["degraded_plan"], p["pair_id"]


# ---------------------------------------------------------------------------
# Pair fields: holdout field set (no target_dimensions).
# ---------------------------------------------------------------------------


def test_holdout_pair_fields_exact(pairs):
    expected = set(HOLDOUT_PAIR_FIELDS)
    for p in pairs:
        assert set(p.keys()) == expected, f"{p['pair_id']} keys {sorted(p.keys())}"


def test_no_target_dimensions_in_pairs(pairs):
    for p in pairs:
        assert "target_dimensions" not in p, p["pair_id"]


def test_expected_flags_use_frozen_flag_names(pairs):
    for p in pairs:
        for flag in p["expected_flags"]:
            assert flag in CRITICAL_FLAGS, f"{p['pair_id']} bad flag {flag}"


# ---------------------------------------------------------------------------
# Validator: unknown field / invalid flag rejected.
# ---------------------------------------------------------------------------


def test_unknown_top_level_field_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["surprise_field"] = "x"
    rep = validate_holdout_dataset(_write(tmp_path, broken))
    assert not rep.all_passed
    assert any("unexpected top-level field" in e.message for e in rep.case_errors)


def test_target_dimensions_hardcoded_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["target_dimensions"] = ["pedagogical_intent_fidelity"]
    rep = validate_holdout_dataset(_write(tmp_path, broken))
    assert not rep.all_passed
    assert any("target_dimensions must not be hardcoded" in e.message for e in rep.case_errors)


def test_invalid_expected_flag_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["expected_flags"] = ["not_a_flag"]
    rep = validate_holdout_dataset(_write(tmp_path, broken))
    assert not rep.all_passed
    assert any("not a frozen critical flag" in e.message for e in rep.case_errors)


def test_structural_defect_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["degraded_plan"]["verbal_plan"]["segments"][0].pop("text")
    rep = validate_holdout_dataset(_write(tmp_path, broken))
    assert not rep.all_passed
    assert any(e.stage == "degraded_plan" for e in rep.case_errors)


# ---------------------------------------------------------------------------
# Separation from development dataset.
# ---------------------------------------------------------------------------


def test_no_id_collision_with_development():
    dev = load_diagnostic_pairs()  # v0.1 development
    holdout = load_diagnostic_pairs(HOLDOUT_DATASET_PATH)
    dev_ids = {p["pair_id"] for p in dev}
    for p in holdout:
        assert p["pair_id"] not in dev_ids


def test_no_content_anchor_duplicate_with_development():
    dev = load_diagnostic_pairs()
    holdout = load_diagnostic_pairs(HOLDOUT_DATASET_PATH)
    dev_anchors = {p["input"]["instructional_content"]["content_anchor"] for p in dev}
    for p in holdout:
        assert p["input"]["instructional_content"]["content_anchor"] not in dev_anchors


def test_no_verbatim_plan_duplicate_with_development():
    dev = load_diagnostic_pairs()
    holdout = load_diagnostic_pairs(HOLDOUT_DATASET_PATH)
    dev_plans = {
        json.dumps(p["reference_plan"], ensure_ascii=False, sort_keys=True) for p in dev
    } | {
        json.dumps(p["degraded_plan"], ensure_ascii=False, sort_keys=True) for p in dev
    }
    for p in holdout:
        for key in ("reference_plan", "degraded_plan"):
            plan_sig = json.dumps(p[key], ensure_ascii=False, sort_keys=True)
            assert plan_sig not in dev_plans, f"{p['pair_id']} {key} duplicates development"


# ---------------------------------------------------------------------------
# No API / no scoring (safety).
# ---------------------------------------------------------------------------


def test_holdout_pairs_contain_no_scores(pairs):
    """Holdout pairs must not contain any Judge score fields."""
    for p in pairs:
        s = json.dumps(p, ensure_ascii=False)
        assert "overall_score" not in s
        assert "structural_valid" not in s
