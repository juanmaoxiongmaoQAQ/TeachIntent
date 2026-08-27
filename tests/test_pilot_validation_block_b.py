"""Focused tests for Block B (cross_domain_generalization) pilot validation.

The frozen Block B dataset is never modified. Tests that need a broken dataset
load the real cases, mutate a copy in memory, and write a temporary JSONL file
to pytest's ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.pilot_validation import (
    BLOCK_B,
    BLOCK_B_DATASET_PATH,
    PILOT_DATASET_PATH,
    validate_pilot_cases,
)


def _load_block_b_cases() -> list[dict]:
    cases: list[dict] = []
    with BLOCK_B_DATASET_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


@pytest.fixture
def block_b_cases() -> list[dict]:
    return _load_block_b_cases()


@pytest.fixture
def tmp_dataset(tmp_path) -> Path:
    """Helper path factory: write a list of cases to a temp JSONL file."""
    def _write(cases: list[dict]) -> Path:
        path = tmp_path / "block_b.jsonl"
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


def test_frozen_block_b_passes_all_checks() -> None:
    report = validate_pilot_cases(BLOCK_B_DATASET_PATH)
    assert report.block == BLOCK_B
    assert report.parsed_count == 12
    assert report.json_schema_pass_count == 12
    assert report.pydantic_pass_count == 12
    assert report.case_errors == []
    for name, detail in report.dataset_checks.items():
        assert detail == "", f"dataset check {name!r} failed: {detail}"
    assert report.all_passed is True


def test_frozen_block_a_still_passes_unchanged() -> None:
    """Block A validation semantics must be preserved exactly."""
    report = validate_pilot_cases(PILOT_DATASET_PATH)
    assert report.block == "controlled_contrast"
    assert report.parsed_count == 12
    assert report.all_passed is True
    # Block A-specific checks are still present with their original names.
    assert "contrast_group_counts" in report.dataset_checks
    assert "case_id_anchor_mapping" in report.dataset_checks
    assert report.dataset_checks["contrast_group_counts"] == ""
    assert report.dataset_checks["case_id_anchor_mapping"] == ""


def test_block_b_expected_check_names() -> None:
    """Block B runs the shared checks plus its own block-specific ones."""
    report = validate_pilot_cases(BLOCK_B_DATASET_PATH)
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
        # Block B specific
        "case_id_format",
        "subject_coverage",
        "learner_level_coverage",
        "learner_utterance_count",
        "affective_state_count",
        "delivery_need_distribution",
    }
    assert set(report.dataset_checks) == expected


# ---------------------------------------------------------------------------
# Unexpected contrast_group in Block B fails (wrapper structure).
# ---------------------------------------------------------------------------


def test_unexpected_contrast_group_in_block_b_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    cases[0]["tags"]["contrast_group"] = "anchor_01"  # Block A field in Block B
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
# Wrong intent distribution fails.
# ---------------------------------------------------------------------------


def test_wrong_intent_distribution_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
    # Flip one elicitation case to a third scaffolding.
    for case in cases:
        if case["case_id"] == "PILOT-B-ELI-01":
            case["input"]["pedagogical_intent"]["primary"] = "scaffolding"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["intent_counts"] != ""
    assert "elicitation" in report.dataset_checks["intent_counts"]
    # case_id_format also fails: ELI-01 now carries scaffolding.
    assert report.dataset_checks["case_id_format"] != ""
    assert not report.all_passed


def test_case_id_intent_mismatch_fails(block_b_cases, tmp_dataset) -> None:
    """A case id abbreviation inconsistent with the runtime intent fails."""
    cases = _copy(block_b_cases)
    # Rename ELI-01 to SCA-99: format OK but intent mismatch.
    cases[0]["case_id"] = "PILOT-B-SCA-99"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_id_format"] != ""
    assert "intent mismatch" in report.dataset_checks["case_id_format"]
    assert not report.all_passed


def test_case_id_bad_format_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
    cases[0]["case_id"] = "PILOT-A-ELI-01"  # wrong block prefix
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_id_format"] != ""
    assert "format" in report.dataset_checks["case_id_format"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Subject coverage fails.
# ---------------------------------------------------------------------------


def test_missing_subject_coverage_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
    # The only physics case (PILOT-B-EXT-01) becomes mathematics -> physics missing.
    for case in cases:
        if case["case_id"] == "PILOT-B-EXT-01":
            case["input"]["instructional_content"]["subject"] = "mathematics"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["subject_coverage"] != ""
    assert "physics" in report.dataset_checks["subject_coverage"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Learner-level coverage fails.
# ---------------------------------------------------------------------------


def test_missing_learner_level_coverage_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
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
# Invalid delivery_need fails.
# ---------------------------------------------------------------------------


def test_invalid_delivery_need_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
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
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    # Change one 'low' case to 'medium': low=6, medium=5.
    for case in cases:
        if case["case_id"] == "PILOT-B-ELI-01":
            case["tags"]["delivery_need"] = "medium"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["delivery_need_distribution"] != ""
    assert "low=6" in report.dataset_checks["delivery_need_distribution"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong learner_utterance count fails.
# ---------------------------------------------------------------------------


def test_wrong_learner_utterance_count_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    # Remove one learner_utterance (10 -> 9).
    for case in cases:
        if case["case_id"] == "PILOT-B-ELI-01":
            del case["input"]["pedagogical_context"]["learner_utterance"]
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["learner_utterance_count"] != ""
    assert "got 9" in report.dataset_checks["learner_utterance_count"]
    assert not report.all_passed


def test_too_many_learner_utterances_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
    # Add learner_utterance to a case missing it (10 -> 11).
    for case in cases:
        if "learner_utterance" not in case["input"]["pedagogical_context"]:
            case["input"]["pedagogical_context"]["learner_utterance"] = "多说一句。"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["learner_utterance_count"] != ""
    assert "got 11" in report.dataset_checks["learner_utterance_count"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong affective_state count fails.
# ---------------------------------------------------------------------------


def test_wrong_affective_state_count_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    # Add affective_state to one more case (3 -> 4).
    for case in cases:
        if "affective_state" not in case["input"]["learner"]:
            case["input"]["learner"]["affective_state"] = "curious"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["affective_state_count"] != ""
    assert "got 4" in report.dataset_checks["affective_state_count"]
    assert not report.all_passed


def test_too_few_affective_states_fails(block_b_cases, tmp_dataset) -> None:
    cases = _copy(block_b_cases)
    # Remove one affective_state (3 -> 2).
    for case in cases:
        if "affective_state" in case["input"]["learner"]:
            del case["input"]["learner"]["affective_state"]
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["affective_state_count"] != ""
    assert "got 2" in report.dataset_checks["affective_state_count"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Strict wrapper validation remains intact for Block B.
# ---------------------------------------------------------------------------


def test_block_b_missing_top_level_field_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    del cases[0]["design_expectations"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "design_expectations" in wrapper_errors[0].message
    assert not report.all_passed


def test_block_b_unexpected_top_level_field_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
    cases[0]["experimenter_notes"] = "not allowed"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "experimenter_notes" in wrapper_errors[0].message
    assert not report.all_passed


def test_block_b_missing_delivery_need_tag_fails(
    block_b_cases, tmp_dataset
) -> None:
    cases = _copy(block_b_cases)
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


def test_explicit_block_param_validates_block_b() -> None:
    report = validate_pilot_cases(BLOCK_B_DATASET_PATH, expected_block=BLOCK_B)
    assert report.block == BLOCK_B
    assert report.all_passed is True


def test_explicit_wrong_block_param_fails() -> None:
    """Passing Block A as expected block for the Block B dataset fails."""
    report = validate_pilot_cases(
        BLOCK_B_DATASET_PATH, expected_block="controlled_contrast"
    )
    assert not report.all_passed
    # Block A's tags contract (delivery_need + contrast_group) fails at the
    # wrapper level for every Block B case (contrast_group missing), so no
    # case reaches dataset-level checks and case_count also fails.
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 12
    assert all("contrast_group" in e.message for e in wrapper_errors)
    assert report.dataset_checks["case_count"] != ""
