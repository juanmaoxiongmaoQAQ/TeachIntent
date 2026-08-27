"""Tests for the Block A pilot dataset validation logic.

The frozen dataset itself is never modified. Tests that need a broken dataset
load the real cases, mutate a copy in memory, and write a temporary JSONL file
to pytest's ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teachintent.pilot_validation import (
    EXPECTED_CASE_COUNT,
    PILOT_DATASET_PATH,
    validate_pilot_cases,
)


def _load_real_cases() -> list[dict]:
    """Load the 12 frozen Block A cases as a list of dicts."""
    cases: list[dict] = []
    with PILOT_DATASET_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _write_jsonl(path: Path, cases: list[dict]) -> Path:
    """Write *cases* as JSONL to *path*."""
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    return path


@pytest.fixture
def real_cases() -> list[dict]:
    return _load_real_cases()


@pytest.fixture
def tmp_dataset(tmp_path) -> Path:
    """Helper path factory: write a list of cases to a temp JSONL file."""
    written: list[Path] = []

    def _write(cases: list[dict]) -> Path:
        path = tmp_path / "block_a.jsonl"
        _write_jsonl(path, cases)
        written.append(path)
        return path

    return _write


# ---------------------------------------------------------------------------
# Valid frozen dataset.
# ---------------------------------------------------------------------------


def test_frozen_block_a_dataset_passes_all_checks() -> None:
    report = validate_pilot_cases(PILOT_DATASET_PATH)
    assert report.parsed_count == EXPECTED_CASE_COUNT
    assert report.json_schema_pass_count == EXPECTED_CASE_COUNT
    assert report.pydantic_pass_count == EXPECTED_CASE_COUNT
    assert report.case_errors == []
    for name, detail in report.dataset_checks.items():
        assert detail == "", f"dataset check {name!r} failed: {detail}"
    assert report.all_passed is True


# ---------------------------------------------------------------------------
# Duplicate case ID.
# ---------------------------------------------------------------------------


def test_duplicate_case_id_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    # Make case 2 share case 1's id.
    cases[1]["case_id"] = cases[0]["case_id"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["unique_case_ids"] != ""
    assert "duplicate" in report.dataset_checks["unique_case_ids"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong intent count.
# ---------------------------------------------------------------------------


def test_wrong_intent_count_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    # Flip one elicitation case to a third scaffolding -> scaffolding=3, elicitation=1.
    for case in cases:
        if case["case_id"] == "PILOT-A-ELI-01":
            case["input"]["pedagogical_intent"]["primary"] = "scaffolding"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["intent_counts"] != ""
    assert "elicitation" in report.dataset_checks["intent_counts"]
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrong contrast group.
# ---------------------------------------------------------------------------


def test_wrong_contrast_group_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    # Flip one anchor_01 case to anchor_02 -> 5/7 split.
    for case in cases:
        if case["case_id"] == "PILOT-A-ELI-01":
            case["tags"]["contrast_group"] = "anchor_02"
            break
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["contrast_group_counts"] != ""
    # Also the case_id->anchor mapping check should fire.
    assert report.dataset_checks["case_id_anchor_mapping"] != ""
    assert not report.all_passed


def test_case_id_anchor_mapping_mismatch_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    # Keep contrast_group counts balanced by swapping two groups between a -01 and -02.
    for case in cases:
        if case["case_id"] == "PILOT-A-ELI-01":
            case["tags"]["contrast_group"] = "anchor_02"
        if case["case_id"] == "PILOT-A-ELI-02":
            case["tags"]["contrast_group"] = "anchor_01"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["case_id_anchor_mapping"] != ""
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Malformed runtime input.
# ---------------------------------------------------------------------------


def test_malformed_runtime_input_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    # Break one case's input: wrong schema_version (const mismatch).
    cases[0]["input"]["schema_version"] = "1.0.0-rc.3"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.json_schema_pass_count == EXPECTED_CASE_COUNT - 1
    assert any(
        err.stage == "json_schema" and err.case_id == cases[0]["case_id"]
        for err in report.case_errors
    )
    assert not report.all_passed


def test_malformed_input_bad_intent_enum_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["input"]["pedagogical_intent"]["primary"] = "out_of_scope"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert any(err.stage == "json_schema" for err in report.case_errors)
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Malformed design expectations.
# ---------------------------------------------------------------------------


def test_malformed_design_expectations_empty_must_fails(
    real_cases, tmp_dataset
) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["design_expectations"]["must"] = []
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["design_expectations"] != ""
    assert "must" in report.dataset_checks["design_expectations"]
    assert not report.all_passed


def test_malformed_design_expectations_non_string_must_not_fails(
    real_cases, tmp_dataset
) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["design_expectations"]["must_not"] = ["ok", 42]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["design_expectations"] != ""
    assert not report.all_passed


def test_missing_design_expectations_field_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    del cases[0]["design_expectations"]["must"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    assert report.dataset_checks["design_expectations"] != ""
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Malformed JSONL line.
# ---------------------------------------------------------------------------


def test_malformed_json_line_is_reported_with_line_number(
    real_cases, tmp_path
) -> None:
    path = tmp_path / "block_a.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(real_cases[0], ensure_ascii=False) + "\n")
        handle.write("{not valid json\n")  # line 2
        handle.write(json.dumps(real_cases[1], ensure_ascii=False) + "\n")
    report = validate_pilot_cases(path)
    parse_errors = [e for e in report.case_errors if e.stage == "json_parse"]
    assert len(parse_errors) == 1
    assert parse_errors[0].line_number == 2
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Experiment metadata is not treated as runtime input.
# ---------------------------------------------------------------------------


def test_experiment_metadata_rejected_at_wrapper_level(
    real_cases, tmp_dataset
) -> None:
    """An extra experiment-only top-level field is rejected at the wrapper
    structure stage, so the case never reaches runtime validation - the
    metadata is certainly not passed into the runtime validators."""
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["experimenter_notes"] = "internal annotation, not runtime input"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    # The extra field is a wrapper_structure error.
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "experimenter_notes" in wrapper_errors[0].message
    # That case did not pass runtime validation (it was skipped).
    assert report.pydantic_pass_count == EXPECTED_CASE_COUNT - 1
    assert not report.all_passed


# ---------------------------------------------------------------------------
# Wrapper structure: missing and unexpected top-level / tags fields.
# ---------------------------------------------------------------------------


def test_missing_top_level_field_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    del cases[0]["block"]
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "block" in wrapper_errors[0].message
    assert "missing top-level" in wrapper_errors[0].message
    assert not report.all_passed


def test_unexpected_top_level_field_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["unexpected_top"] = "value"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "unexpected_top" in wrapper_errors[0].message
    assert "unexpected top-level" in wrapper_errors[0].message
    assert not report.all_passed


def test_missing_tags_field_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
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


def test_unexpected_tags_field_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["tags"]["unexpected_tag"] = "value"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "unexpected_tag" in wrapper_errors[0].message
    assert "unexpected tags" in wrapper_errors[0].message
    assert not report.all_passed


def test_tags_not_an_object_fails(real_cases, tmp_dataset) -> None:
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    cases[0]["tags"] = "not-an-object"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    assert "tags is not an object" in wrapper_errors[0].message
    assert not report.all_passed


def test_multiple_wrapper_issues_reported_together(real_cases, tmp_dataset) -> None:
    """A case with both a missing and an unexpected top-level field reports
    both issues in a single wrapper_structure error."""
    cases = [json.loads(json.dumps(c)) for c in real_cases]
    del cases[0]["difficulty"]
    cases[0]["extra"] = "value"
    path = tmp_dataset(cases)
    report = validate_pilot_cases(path)
    wrapper_errors = [
        e for e in report.case_errors if e.stage == "wrapper_structure"
    ]
    assert len(wrapper_errors) == 1
    msg = wrapper_errors[0].message
    assert "difficulty" in msg and "missing top-level" in msg
    assert "extra" in msg and "unexpected top-level" in msg
    assert not report.all_passed
