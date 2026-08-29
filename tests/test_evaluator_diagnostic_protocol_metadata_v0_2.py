"""Tests for the Protocol v0.2 coupling-matrix metadata validator.

All offline. Verifies: 8 families present, pairwise disjoint partition,
completeness (union == D1-D6), no unknown dimension, no omitted dimension, and
rejection of overlap / missing / unknown dimensions.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from teachintent.evaluator_diagnostic import (
    PROTOCOL_METADATA_PATH,
    validate_protocol_metadata,
)
from teachintent.evaluator.rubric import DIMENSION_IDS


@pytest.fixture(scope="module")
def metadata() -> dict:
    with PROTOCOL_METADATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report():
    return validate_protocol_metadata()


def _write(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Metadata validates cleanly.
# ---------------------------------------------------------------------------


def test_metadata_all_passed(report):
    assert report.all_passed
    assert not report.case_errors


def test_protocol_version_is_v0_2(metadata):
    assert metadata["protocol_version"] == "v0.2"


def test_all_8_families_present(metadata):
    from teachintent.evaluator_diagnostic import DIAGNOSTIC_FAMILIES
    assert set(metadata["families"].keys()) == set(DIAGNOSTIC_FAMILIES)


def test_each_family_has_three_groups(metadata):
    for fam, entry in metadata["families"].items():
        for key in (
            "primary_target_dimensions",
            "allowed_collateral_dimensions",
            "protected_dimensions",
        ):
            assert key in entry, f"{fam} missing {key}"
            assert isinstance(entry[key], list), f"{fam} {key} not a list"


# ---------------------------------------------------------------------------
# Disjointness + completeness (Section 8 invariants).
# ---------------------------------------------------------------------------


def test_partition_disjoint(metadata):
    for fam, entry in metadata["families"].items():
        primary = set(entry["primary_target_dimensions"])
        collateral = set(entry["allowed_collateral_dimensions"])
        protected = set(entry["protected_dimensions"])
        assert primary & collateral == set(), fam
        assert primary & protected == set(), fam
        assert collateral & protected == set(), fam


def test_partition_complete(metadata):
    for fam, entry in metadata["families"].items():
        union = (
            set(entry["primary_target_dimensions"])
            | set(entry["allowed_collateral_dimensions"])
            | set(entry["protected_dimensions"])
        )
        assert union == set(DIMENSION_IDS), f"{fam} union={sorted(union)}"


def test_no_unknown_dimension(metadata):
    for fam, entry in metadata["families"].items():
        all_dims = (
            set(entry["primary_target_dimensions"])
            | set(entry["allowed_collateral_dimensions"])
            | set(entry["protected_dimensions"])
        )
        assert all_dims <= set(DIMENSION_IDS), f"{fam} unknown dims"


def test_frozen_matrix_matches_protocol_section_9():
    """Spot-check the frozen coupling matrix values against Protocol Section 9."""
    fams = validate_protocol_metadata  # noqa
    with PROTOCOL_METADATA_PATH.open(encoding="utf-8") as f:
        doc = json.load(f)
    f = doc["families"]

    # Family A: primary D1, collateral D4.
    assert f["intent_mismatch"]["primary_target_dimensions"] == ["pedagogical_intent_fidelity"]
    assert f["intent_mismatch"]["allowed_collateral_dimensions"] == ["intent_specific_instructional_adequacy"]

    # Family E: primary D4, collateral none.
    assert f["incomplete_corrective_feedback"]["primary_target_dimensions"] == ["intent_specific_instructional_adequacy"]
    assert f["incomplete_corrective_feedback"]["allowed_collateral_dimensions"] == []

    # Family G: primary D6, collateral D3+D5.
    assert f["delivery_pedagogy_conflict"]["primary_target_dimensions"] == ["delivery_pedagogy_alignment"]
    assert set(f["delivery_pedagogy_conflict"]["allowed_collateral_dimensions"]) == {
        "learner_state_compatibility", "delivery_necessity_sparsity"
    }


# ---------------------------------------------------------------------------
# Validator: rejection of broken metadata.
# ---------------------------------------------------------------------------


def test_overlap_rejected(tmp_path, metadata):
    doc = copy.deepcopy(metadata)
    fam = doc["families"]["intent_mismatch"]
    fam["allowed_collateral_dimensions"] = ["pedagogical_intent_fidelity"]  # overlaps primary
    rep = validate_protocol_metadata(_write(tmp_path, doc))
    assert not rep.all_passed
    assert any("primary ∩ collateral" in e for e in rep.case_errors)


def test_missing_dimension_rejected(tmp_path, metadata):
    doc = copy.deepcopy(metadata)
    fam = doc["families"]["intent_mismatch"]
    # Drop a protected dimension -> union no longer covers D1-D6.
    fam["protected_dimensions"] = [
        d for d in fam["protected_dimensions"] if d != "delivery_pedagogy_alignment"
    ]
    rep = validate_protocol_metadata(_write(tmp_path, doc))
    assert not rep.all_passed
    assert any("omitted dimension" in e for e in rep.case_errors)


def test_unknown_dimension_rejected(tmp_path, metadata):
    doc = copy.deepcopy(metadata)
    fam = doc["families"]["intent_mismatch"]
    fam["primary_target_dimensions"] = ["not_a_dimension"]
    rep = validate_protocol_metadata(_write(tmp_path, doc))
    assert not rep.all_passed
    assert any("unknown dimension" in e for e in rep.case_errors)


def test_missing_family_rejected(tmp_path, metadata):
    doc = copy.deepcopy(metadata)
    del doc["families"]["content_contradiction"]
    rep = validate_protocol_metadata(_write(tmp_path, doc))
    assert not rep.all_passed
    assert "missing families" in rep.checks.get("family_coverage", "")


def test_wrong_protocol_version_rejected(tmp_path, metadata):
    doc = copy.deepcopy(metadata)
    doc["protocol_version"] = "v0.1"
    rep = validate_protocol_metadata(_write(tmp_path, doc))
    assert not rep.all_passed
    assert any("protocol_version" in e for e in rep.case_errors)
