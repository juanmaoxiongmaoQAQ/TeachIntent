"""Tests for the diagnostic pairs dataset contract and validator.

All offline. Verifies the mechanical contract: family counts, pair ID
uniqueness/format, input/plan Layer-0 validity, dimension/flag enums,
unknown-field rejection, and reference != degraded.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_DATASET_PATH,
    DIAGNOSTIC_FAMILIES,
    EXPECTED_PAIR_COUNT,
    EXPECTED_PAIR_FIELDS,
    PAIRS_PER_FAMILY,
    load_diagnostic_pairs,
    validate_diagnostic_dataset,
)
from teachintent.evaluator.rubric import CRITICAL_FLAGS, DIMENSION_IDS


@pytest.fixture(scope="module")
def pairs() -> list[dict]:
    return load_diagnostic_pairs()


@pytest.fixture(scope="module")
def report():
    return validate_diagnostic_dataset()


def _write_pairs(tmp_path: Path, pairs: list[dict]) -> Path:
    path = tmp_path / "pairs.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for p in pairs:
            handle.write(json.dumps(p, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Family counts.
# ---------------------------------------------------------------------------


def test_exactly_24_pairs(pairs):
    assert len(pairs) == EXPECTED_PAIR_COUNT == 24


def test_exactly_8_families(pairs):
    families = {p["family"] for p in pairs}
    assert families == set(DIAGNOSTIC_FAMILIES)
    assert len(families) == 8


def test_3_pairs_per_family(pairs):
    from collections import Counter
    counts = Counter(p["family"] for p in pairs)
    assert all(n == PAIRS_PER_FAMILY for n in counts.values())
    assert set(counts) == set(DIAGNOSTIC_FAMILIES)


# ---------------------------------------------------------------------------
# Pair ID uniqueness / format.
# ---------------------------------------------------------------------------


def test_pair_ids_unique(pairs):
    ids = [p["pair_id"] for p in pairs]
    assert len(ids) == len(set(ids)) == 24


def test_pair_id_format(pairs):
    import re
    pattern = re.compile(r"^DIAG-[A-H]-\d{2}$")
    for p in pairs:
        assert pattern.match(p["pair_id"]), f"bad pair_id {p['pair_id']}"


def test_pair_id_prefix_matches_family(pairs):
    from teachintent.evaluator_diagnostic.dataset import FAMILY_PAIR_ID_PREFIXES
    for p in pairs:
        letter = p["pair_id"][5]
        assert FAMILY_PAIR_ID_PREFIXES[letter] == p["family"]


# ---------------------------------------------------------------------------
# Dataset validates cleanly.
# ---------------------------------------------------------------------------


def test_frozen_dataset_all_passed(report):
    assert report.all_passed
    assert report.parsed_count == 24
    assert report.input_pass_count == 24
    assert report.reference_pass_count == 24
    assert report.degraded_pass_count == 24
    assert not report.case_errors


def test_all_plans_layer0_valid(pairs):
    """Both reference and degraded plans pass Layer 0 (JSON Schema + Pydantic)."""
    from teachintent.models import SpeechPlan
    from teachintent.validators import iter_speech_plan_errors
    for p in pairs:
        for key in ("reference_plan", "degraded_plan"):
            plan = p[key]
            assert not list(iter_speech_plan_errors(plan)), f"{p['pair_id']} {key} schema errors"
            SpeechPlan.model_validate(plan)  # must not raise


def test_all_inputs_valid(pairs):
    from teachintent.models import TeachIntentInput
    from teachintent.validators import iter_input_errors
    for p in pairs:
        assert not list(iter_input_errors(p["input"])), f"{p['pair_id']} input schema errors"
        TeachIntentInput.model_validate(p["input"])


def test_reference_neq_degraded(pairs):
    for p in pairs:
        assert p["reference_plan"] != p["degraded_plan"], p["pair_id"]


# ---------------------------------------------------------------------------
# target_dimensions / expected_flags enums.
# ---------------------------------------------------------------------------


def test_target_dimensions_use_frozen_dimension_ids(pairs):
    for p in pairs:
        assert p["target_dimensions"], f"{p['pair_id']} empty target_dimensions"
        for dim in p["target_dimensions"]:
            assert dim in DIMENSION_IDS, f"{p['pair_id']} bad dim {dim}"


def test_expected_flags_use_frozen_flag_names(pairs):
    for p in pairs:
        for flag in p["expected_flags"]:
            assert flag in CRITICAL_FLAGS, f"{p['pair_id']} bad flag {flag}"


# ---------------------------------------------------------------------------
# Validator: unknown fields rejected.
# ---------------------------------------------------------------------------


def test_unknown_top_level_field_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["surprise_field"] = "x"
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any(e.stage == "wrapper" and "unexpected top-level" in e.message for e in rep.case_errors)


# ---------------------------------------------------------------------------
# Validator: invalid target dimension / expected flag rejected.
# ---------------------------------------------------------------------------


def test_invalid_target_dimension_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["target_dimensions"] = ["not_a_dimension"]
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any("not a frozen D1-D6 id" in e.message for e in rep.case_errors)


def test_invalid_expected_flag_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["expected_flags"] = ["not_a_flag"]
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any("not a frozen critical flag" in e.message for e in rep.case_errors)


# ---------------------------------------------------------------------------
# Validator: family enum / count errors.
# ---------------------------------------------------------------------------


def test_unknown_family_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["family"] = "not_a_family"
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any("not in frozen family enum" in e.message for e in rep.case_errors)


def test_wrong_pair_count_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs[:23])  # 23 instead of 24
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert "pair_count" in rep.dataset_checks and rep.dataset_checks["pair_count"] != ""


def test_wrong_pairs_per_family_rejected(tmp_path, pairs):
    # Duplicate an A pair and drop a B pair -> family imbalance.
    broken = copy.deepcopy(pairs)
    # Replace DIAG-B-01 with a copy of DIAG-A-01 (keeping family field consistent).
    a_pair = copy.deepcopy(broken[0])
    broken[3] = a_pair  # DIAG-B-01 slot
    broken[3]["pair_id"] = "DIAG-B-01"
    broken[3]["family"] = "intent_mismatch"
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed


def test_duplicate_pair_id_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[1]["pair_id"] = broken[0]["pair_id"]
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert "duplicate pair_id" in rep.dataset_checks["unique_pair_ids"]


# ---------------------------------------------------------------------------
# Validator: malformed JSON / structural defects rejected.
# ---------------------------------------------------------------------------


def test_malformed_json_rejected(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"pair_id": "DIAG-A-01", "family":', encoding="utf-8")
    rep = validate_diagnostic_dataset(path)
    assert not rep.all_passed
    assert any(e.stage == "json_parse" for e in rep.case_errors)


def test_degraded_plan_structural_defect_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    # Missing required field -> Layer 0 structural failure.
    broken[0]["degraded_plan"]["verbal_plan"]["segments"][0].pop("text")
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any(e.stage == "degraded_plan" for e in rep.case_errors)


def test_reference_plan_structural_defect_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["reference_plan"].pop("delivery_plan")
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any(e.stage == "reference_plan" for e in rep.case_errors)


def test_input_defect_rejected(tmp_path, pairs):
    broken = copy.deepcopy(pairs)
    broken[0]["input"].pop("pedagogical_intent")
    rep = validate_diagnostic_dataset(_write_pairs(tmp_path, broken))
    assert not rep.all_passed
    assert any(e.stage == "input" for e in rep.case_errors)
