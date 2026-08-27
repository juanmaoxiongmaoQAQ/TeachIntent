"""Focused tests for Block C (hard_adversarial) pilot validation.

The frozen Block C dataset is never modified. Tests that need a broken dataset
load the real cases, mutate a copy in memory, and write a temporary JSONL file
to pytest's ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.pilot_validation import (
    BLOCK_A,
    BLOCK_B,
    BLOCK_C,
    BLOCK_C_DATASET_PATH,
    PILOT_DATASET_PATH,
    BLOCK_B_DATASET_PATH,
    validate_pilot_cases,
)


def _load_block_c_cases() -> list[dict]:
    cases: list[dict] = []
    with BLOCK_C_DATASET_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


@pytest.fixture
def block_c_cases() -> list[dict]:
    return _load_block_c_cases()


@pytest.fixture
def tmp_dataset(tmp_path) -> Path:
    """Helper path factory: write a list of cases to a temp JSONL file."""
    def _write(cases: list[dict]) -> Path:
        path = tmp_path / "block_c.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(json.dumps(case, ensure_ascii=False) + "\n")
        return path

    return _write


def _copy(cases: list[dict]) -> list[dict]:
    return [json.loads(json.dumps(c)) for c in cases]


# ---------------------------------------------------------------------------
# Frozen datasets pass.
# ---------------------------------------------------------------------------


def test_frozen_block_c_passes_all_checks() -> None:
    report = validate_pilot_cases(BLOCK_C_DATASET_PATH)
    assert report.block == BLOCK_C
    assert report.parsed_count == 6
    assert report.json_schema_pass_count == 6
    assert report.pydantic_pass_count == 6
    assert report.case_errors == []
    for name, detail in report.dataset_checks.items():
        assert detail == "", f"dataset check {name!r} failed: {detail}"
    assert report.all_passed is True


def test_frozen_block_a_still_passes_unchanged() -> None:
    report = validate_pilot_cases(PILOT_DATASET_PATH)
    assert report.block == BLOCK_A
    assert report.all_passed is True


def test_frozen_block_b_still_passes_unchanged() -> None:
    report = validate_pilot_cases(BLOCK_B_DATASET_PATH)
    assert report.block == BLOCK_B
    assert report.all_passed is True


def test_block_c_expected_check_names() -> None:
    report = validate_pilot_cases(BLOCK_C_DATASET_PATH)
    expected = {
        # shared
        "case_count",
        "unique_case_ids",
        "block_value",
        "difficulty_value",
        "schema_version",
        "output_language",
        "intent_counts",
        "delivery_need_values",
        "design_expectations",
        # Block C specific
        "case_id_format",
        "subject_coverage",
        "learner_level_coverage",
        "delivery_need_distribution",
    }
    assert set(report.dataset_checks) == expected


# ---------------------------------------------------------------------------
# Wrong case count fails.
# ---------------------------------------------------------------------------


def test_wrong_case_count_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # Add a duplicate of the first case to make 7 cases.
    cases.append(json.loads(json.dumps(cases[0])))
    cases[-1]["case_id"] = "PILOT-C-EXT-02"  # unique id but 7th case
    cases[-1]["input"]["pedagogical_intent"]["primary"] = "extension"
    cases[-1]["input"]["instructional_content"]["subject"] = "biology"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_count"] != ""
    assert "expected 6" in report.dataset_checks["case_count"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Duplicate IDs fail.
# ---------------------------------------------------------------------------


def test_duplicate_case_ids_fail(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[1]["case_id"] = cases[0]["case_id"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["unique_case_ids"] != ""
    assert "duplicate" in report.dataset_checks["unique_case_ids"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong difficulty fails.
# ---------------------------------------------------------------------------


def test_wrong_difficulty_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["difficulty"] = "standard"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["difficulty_value"] != ""
    assert "standard" in report.dataset_checks["difficulty_value"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong intent distribution fails.
# ---------------------------------------------------------------------------


def test_wrong_intent_distribution_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # Flip elicitation to a second scaffolding: scaffolding=2, elicitation=0.
    cases[0]["input"]["pedagogical_intent"]["primary"] = "scaffolding"
    # Fix the case_id to match the new intent so case_id_format doesn't mask
    # the intent_counts failure.
    cases[0]["case_id"] = "PILOT-C-SCA-02"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["intent_counts"] != ""
    assert "elicitation=0" in report.dataset_checks["intent_counts"]
    assert "scaffolding=2" in report.dataset_checks["intent_counts"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Case ID / intent mismatch fails.
# ---------------------------------------------------------------------------


def test_case_id_intent_mismatch_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # Rename ELI-01 to SCA-01: format OK but intent mismatch.
    cases[0]["case_id"] = "PILOT-C-SCA-01"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_id_format"] != ""
    assert "intent mismatch" in report.dataset_checks["case_id_format"]
    assert not report.all_passed


def test_case_id_bad_format_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["case_id"] = "PILOT-A-ELI-01"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_id_format"] != ""
    assert "format" in report.dataset_checks["case_id_format"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Unexpected contrast_group fails (wrapper structure).
# ---------------------------------------------------------------------------


def test_unexpected_contrast_group_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["tags"]["contrast_group"] = "anchor_01"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "contrast_group" in wrapper_errors[0].message
    assert "unexpected tags" in wrapper_errors[0].message
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Invalid delivery_need fails.
# ---------------------------------------------------------------------------


def test_invalid_delivery_need_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["tags"]["delivery_need"] = "urgent"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["delivery_need_values"] != ""
    assert "urgent" in report.dataset_checks["delivery_need_values"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong frozen delivery-need distribution fails.
# ---------------------------------------------------------------------------


def test_wrong_delivery_need_distribution_fails(
    block_c_cases, tmp_dataset
) -> None:
    cases = _copy(block_c_cases)
    # Change one 'low' to 'high': low=2, high=4.
    cases[0]["tags"]["delivery_need"] = "high"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["delivery_need_distribution"] != ""
    assert "low=2" in report.dataset_checks["delivery_need_distribution"]
    assert "high=4" in report.dataset_checks["delivery_need_distribution"]
    assert not report.all_passed


def test_medium_delivery_need_fails_distribution(
    block_c_cases, tmp_dataset
) -> None:
    """Block C must have zero medium delivery_need."""
    cases = _copy(block_c_cases)
    cases[0]["tags"]["delivery_need"] = "medium"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["delivery_need_distribution"] != ""
    assert "medium=1" in report.dataset_checks["delivery_need_distribution"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Missing or duplicated subject coverage fails.
# ---------------------------------------------------------------------------


def test_missing_subject_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # The only physics case becomes mathematics -> physics missing.
    for case in cases:
        if case["input"]["instructional_content"]["subject"] == "physics":
            case["input"]["instructional_content"]["subject"] = "mathematics"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["subject_coverage"] != ""
    assert "physics=0" in report.dataset_checks["subject_coverage"]
    assert not report.all_passed


def test_duplicated_subject_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # mathematics appears twice: the biology case becomes mathematics.
    for case in cases:
        if case["input"]["instructional_content"]["subject"] == "biology":
            case["input"]["instructional_content"]["subject"] = "mathematics"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["subject_coverage"] != ""
    assert "mathematics=2" in report.dataset_checks["subject_coverage"]
    assert "biology=0" in report.dataset_checks["subject_coverage"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Invalid / missing learner-level coverage fails.
# ---------------------------------------------------------------------------


def test_elementary_school_not_allowed_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # Change one middle_school to elementary_school -> elementary_school unexpected.
    for case in cases:
        if case["input"]["learner"]["level"] == "middle_school":
            case["input"]["learner"]["level"] = "elementary_school"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["learner_level_coverage"] != ""
    assert "elementary_school" in report.dataset_checks["learner_level_coverage"]
    assert not report.all_passed


def test_missing_high_school_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    # Convert every high_school case to middle_school -> high_school missing.
    for case in cases:
        if case["input"]["learner"]["level"] == "high_school":
            case["input"]["learner"]["level"] = "middle_school"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["learner_level_coverage"] != ""
    assert "high_school" in report.dataset_checks["learner_level_coverage"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Missing / empty must or must_not fails.
# ---------------------------------------------------------------------------


def test_missing_must_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    del cases[0]["design_expectations"]["must"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["design_expectations"] != ""
    assert "must" in report.dataset_checks["design_expectations"]
    assert not report.all_passed


def test_empty_must_not_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["design_expectations"]["must_not"] = []
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["design_expectations"] != ""
    assert "must_not" in report.dataset_checks["design_expectations"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Strict wrapper validation remains intact.
# ---------------------------------------------------------------------------


def test_missing_top_level_field_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    del cases[0]["tags"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "tags" in wrapper_errors[0].message
    assert "missing top-level" in wrapper_errors[0].message
    assert not report.all_passed


def test_unexpected_top_level_field_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    cases[0]["experimenter_notes"] = "not allowed"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "experimenter_notes" in wrapper_errors[0].message
    assert not report.all_passed


def test_missing_delivery_need_tag_fails(block_c_cases, tmp_dataset) -> None:
    cases = _copy(block_c_cases)
    del cases[0]["tags"]["delivery_need"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "delivery_need" in wrapper_errors[0].message
    assert "missing tags" in wrapper_errors[0].message
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Explicit expected_block parameter.
# ---------------------------------------------------------------------------


def test_explicit_block_param_validates_block_c() -> None:
    report = validate_pilot_cases(BLOCK_C_DATASET_PATH, expected_block=BLOCK_C)
    assert report.block == BLOCK_C
    assert report.all_passed is True


def test_explicit_wrong_block_param_fails() -> None:
    """Passing Block A as expected block for the Block C dataset fails."""
    report = validate_pilot_cases(
        BLOCK_C_DATASET_PATH, expected_block="controlled_contrast"
    )
    assert not report.all_passed
    # Block A's tags contract (delivery_need + contrast_group) fails at the
    # wrapper level for every Block C case.
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 6
    assert all("contrast_group" in e.message for e in wrapper_errors)
