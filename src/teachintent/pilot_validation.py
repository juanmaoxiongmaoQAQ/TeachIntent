"""Structural validation for the frozen TeachIntent Block A pilot dataset.

Reuses the frozen runtime contract validators
(``teachintent.validators.iter_input_errors`` and
``teachintent.models.TeachIntentInput``) to validate ONLY ``case["input"]`` per
case. Experiment metadata (``case_id``, ``block``, ``tags``,
``design_expectations``, ...) is never passed into the runtime validators.

Dataset-level checks enforce the Block A controlled-contrast design:
exactly 12 cases, unique case ids, six intents x two anchors, etc.

This module does NOT call Hy3 and requires no API credentials.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .models import TeachIntentInput
from .validators import iter_input_errors

__all__ = [
    "CaseError",
    "ValidationReport",
    "PILOT_DATASET_PATH",
    "EXPECTED_CASE_COUNT",
    "EXPECTED_TOP_FIELDS",
    "EXPECTED_TAGS_FIELDS",
    "SIX_INTENTS",
    "DELIVERY_NEEDS",
    "validate_pilot_cases",
]

# Repository-relative path to the frozen Block A dataset.
PILOT_DATASET_PATH = Path(__file__).resolve().parents[2] / "cases" / "pilot" / "blocks" / "block_a_controlled_contrast.jsonl"

EXPECTED_CASE_COUNT = 12
EXPECTED_TOP_FIELDS = ("case_id", "block", "difficulty", "tags", "input", "design_expectations")
EXPECTED_TAGS_FIELDS = ("delivery_need", "contrast_group")
SIX_INTENTS = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)
DELIVERY_NEEDS = ("low", "medium", "high")
EXPECTED_BLOCK = "controlled_contrast"
EXPECTED_DIFFICULTY = "standard"
EXPECTED_SCHEMA_VERSION = "1.0.0-rc.2"
EXPECTED_OUTPUT_LANGUAGE = "zh-CN"


@dataclass(frozen=True)
class CaseError:
    """A single case-specific validation error."""

    line_number: int
    case_id: str | None
    stage: str  # "json_parse" | "wrapper_structure" | "json_schema" | "pydantic"
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Full validation report for a pilot dataset file."""

    parsed_count: int
    json_schema_pass_count: int
    pydantic_pass_count: int
    # dataset_checks maps check name -> "" (passed) or a human-readable error message.
    dataset_checks: dict[str, str]
    case_errors: list[CaseError] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return (
            not self.case_errors
            and all(v == "" for v in self.dataset_checks.values())
        )


def _anchor_from_case_id(case_id: str) -> str | None:
    """Return 'anchor_01' / 'anchor_02' inferred from a '-01'/'-02' case id suffix."""
    if case_id.endswith("-01"):
        return "anchor_01"
    if case_id.endswith("-02"):
        return "anchor_02"
    return None


def _non_empty_string_list(value: object) -> bool:
    """True if *value* is a non-empty list of non-empty strings."""
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, str) and item for item in value)


def validate_pilot_cases(path: Path) -> ValidationReport:
    """Validate the Block A pilot dataset at *path*.

    Returns a :class:`ValidationReport`. Does not raise on validation failures;
    only raises on I/O errors (file not found, etc.).
    """
    case_errors: list[CaseError] = []
    cases: list[tuple[int, dict]] = []  # (line_number, parsed_case)

    # ---- Stage 1: parse JSONL line by line ----
    with Path(path).open(encoding="utf-8") as handle:
        for index, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue  # skip blank lines (e.g. trailing newline)
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                case_errors.append(
                    CaseError(
                        line_number=index,
                        case_id=None,
                        stage="json_parse",
                        message=f"malformed JSON: {exc.msg} (col {exc.colno})",
                    )
                )
                continue
            if not isinstance(case, dict):
                case_errors.append(
                    CaseError(
                        line_number=index,
                        case_id=None,
                        stage="json_parse",
                        message="JSONL line parsed to a non-object value",
                    )
                )
                continue
            cases.append((index, case))

    parsed_count = len(cases)

    # ---- Stage 2: wrapper structure (top-level + tags fields) ----
    # The experiment wrapper must carry exactly the expected top-level fields
    # and a tags sub-object with exactly the expected tags fields. Missing AND
    # unexpected fields are rejected at this level, before any runtime
    # validation, so experiment metadata is never treated as runtime input.
    well_formed: list[tuple[int, dict]] = []
    for line_number, case in cases:
        case_id = case.get("case_id")
        case_id_str = case_id if isinstance(case_id, str) else None
        issues: list[str] = []

        top_keys = set(case.keys())
        missing_top = [f for f in EXPECTED_TOP_FIELDS if f not in top_keys]
        unexpected_top = sorted(top_keys - set(EXPECTED_TOP_FIELDS))
        if missing_top:
            issues.append(f"missing top-level field(s): {missing_top}")
        if unexpected_top:
            issues.append(f"unexpected top-level field(s): {unexpected_top}")

        # tags sub-object: must be a dict with exactly the expected fields.
        if "tags" in case:
            tags = case["tags"]
            if not isinstance(tags, dict):
                issues.append("tags is not an object")
            else:
                tags_keys = set(tags.keys())
                missing_tags = [f for f in EXPECTED_TAGS_FIELDS if f not in tags_keys]
                unexpected_tags = sorted(tags_keys - set(EXPECTED_TAGS_FIELDS))
                if missing_tags:
                    issues.append(f"missing tags field(s): {missing_tags}")
                if unexpected_tags:
                    issues.append(f"unexpected tags field(s): {unexpected_tags}")

        if issues:
            case_errors.append(
                CaseError(
                    line_number=line_number,
                    case_id=case_id_str,
                    stage="wrapper_structure",
                    message="; ".join(issues),
                )
            )
            continue
        well_formed.append((line_number, case))

    # ---- Stage 3: runtime validation of case["input"] only ----
    json_schema_pass = 0
    pydantic_pass = 0
    runtime_inputs: list[tuple[int, dict, dict]] = []  # (line, input, case)
    for line_number, case in well_formed:
        case_id = case["case_id"]
        input_doc = case["input"]
        if not isinstance(input_doc, dict):
            case_errors.append(
                CaseError(
                    line_number=line_number,
                    case_id=case_id,
                    stage="wrapper_structure",
                    message="case['input'] is not an object",
                )
            )
            continue

        errors = iter_input_errors(input_doc)
        if errors:
            summaries = [f"{e.json_path}: {e.message}" for e in errors]
            case_errors.append(
                CaseError(
                    line_number=line_number,
                    case_id=case_id,
                    stage="json_schema",
                    message="; ".join(summaries),
                )
            )
            continue
        json_schema_pass += 1

        try:
            TeachIntentInput.model_validate(input_doc)
        except ValidationError as exc:
            case_errors.append(
                CaseError(
                    line_number=line_number,
                    case_id=case_id,
                    stage="pydantic",
                    message=str(exc),
                )
            )
            continue
        pydantic_pass += 1
        runtime_inputs.append((line_number, input_doc, case))

    # ---- Stage 4: dataset-level checks (over well-formed, runtime-valid cases) ----
    dataset_checks: dict[str, str] = {}
    valid_cases = [case for _, _, case in runtime_inputs]

    # 4.1 case count
    if len(valid_cases) != EXPECTED_CASE_COUNT:
        dataset_checks["case_count"] = (
            f"expected {EXPECTED_CASE_COUNT} valid cases, got {len(valid_cases)}"
        )
    else:
        dataset_checks["case_count"] = ""

    # 4.2 unique case ids
    case_ids = [c["case_id"] for c in valid_cases]
    id_counts = Counter(case_ids)
    duplicates = sorted(cid for cid, n in id_counts.items() if n > 1)
    dataset_checks["unique_case_ids"] = (
        f"duplicate case_id values: {duplicates}" if duplicates else ""
    )

    # 4.3 block value
    bad_blocks = sorted({c["block"] for c in valid_cases if c["block"] != EXPECTED_BLOCK})
    dataset_checks["block_value"] = (
        f"unexpected block value(s): {bad_blocks}" if bad_blocks else ""
    )

    # 4.4 difficulty value
    bad_difficulty = sorted(
        {c["difficulty"] for c in valid_cases if c["difficulty"] != EXPECTED_DIFFICULTY}
    )
    dataset_checks["difficulty_value"] = (
        f"unexpected difficulty value(s): {bad_difficulty}" if bad_difficulty else ""
    )

    # 4.5 schema_version
    bad_versions = sorted(
        {
            c["input"]["schema_version"]
            for c in valid_cases
            if c["input"].get("schema_version") != EXPECTED_SCHEMA_VERSION
        }
    )
    dataset_checks["schema_version"] = (
        f"unexpected schema_version value(s): {bad_versions}" if bad_versions else ""
    )

    # 4.6 output_language
    bad_langs = sorted(
        {
            c["input"]["output_language"]
            for c in valid_cases
            if c["input"].get("output_language") != EXPECTED_OUTPUT_LANGUAGE
        }
    )
    dataset_checks["output_language"] = (
        f"unexpected output_language value(s): {bad_langs}" if bad_langs else ""
    )

    # 4.7 each of the six intents occurs exactly twice
    intent_counts = Counter(
        c["input"]["pedagogical_intent"]["primary"] for c in valid_cases
    )
    intent_problems = []
    for intent in SIX_INTENTS:
        n = intent_counts.get(intent, 0)
        if n != 2:
            intent_problems.append(f"{intent}={n}")
    extra_intents = sorted(set(intent_counts) - set(SIX_INTENTS))
    for intent in extra_intents:
        intent_problems.append(f"{intent}={intent_counts[intent]} (unexpected)")
    dataset_checks["intent_counts"] = (
        f"intent counts not exactly 2 each: {intent_problems}"
        if intent_problems
        else ""
    )

    # 4.8 exactly six anchor_01 and six anchor_02
    anchor_counts = Counter(c["tags"]["contrast_group"] for c in valid_cases)
    anchor_problems = []
    if anchor_counts.get("anchor_01", 0) != 6:
        anchor_problems.append(f"anchor_01={anchor_counts.get('anchor_01', 0)}")
    if anchor_counts.get("anchor_02", 0) != 6:
        anchor_problems.append(f"anchor_02={anchor_counts.get('anchor_02', 0)}")
    extra_anchors = sorted(set(anchor_counts) - {"anchor_01", "anchor_02"})
    for anchor in extra_anchors:
        anchor_problems.append(f"{anchor}={anchor_counts[anchor]} (unexpected)")
    dataset_checks["contrast_group_counts"] = (
        f"contrast_group counts not 6/6: {anchor_problems}"
        if anchor_problems
        else ""
    )

    # 4.9 case_id suffix maps to matching contrast_group
    mismatches: list[str] = []
    for c in valid_cases:
        case_id = c["case_id"]
        expected_anchor = _anchor_from_case_id(case_id)
        actual_anchor = c["tags"]["contrast_group"]
        if expected_anchor is None:
            mismatches.append(f"{case_id} (unrecognized id suffix)")
        elif actual_anchor != expected_anchor:
            mismatches.append(
                f"{case_id} expects {expected_anchor} but tags.contrast_group={actual_anchor}"
            )
    dataset_checks["case_id_anchor_mapping"] = (
        f"case_id/anchor mismatches: {mismatches}" if mismatches else ""
    )

    # 4.10 delivery_need in {low, medium, high}
    bad_needs = []
    for c in valid_cases:
        need = c["tags"].get("delivery_need")
        if need not in DELIVERY_NEEDS:
            bad_needs.append(f"{c['case_id']}={need!r}")
    dataset_checks["delivery_need_values"] = (
        f"invalid delivery_need value(s): {bad_needs}" if bad_needs else ""
    )

    # 4.11 design_expectations.must / must_not non-empty lists of non-empty strings
    bad_expectations = []
    for c in valid_cases:
        de = c["design_expectations"]
        if not isinstance(de, dict):
            bad_expectations.append(f"{c['case_id']} (design_expectations not an object)")
            continue
        for field_name in ("must", "must_not"):
            value = de.get(field_name)
            if not _non_empty_string_list(value):
                bad_expectations.append(
                    f"{c['case_id']}.design_expectations.{field_name}"
                )
    dataset_checks["design_expectations"] = (
        f"malformed design_expectations field(s): {bad_expectations}"
        if bad_expectations
        else ""
    )

    return ValidationReport(
        parsed_count=parsed_count,
        json_schema_pass_count=json_schema_pass,
        pydantic_pass_count=pydantic_pass,
        dataset_checks=dataset_checks,
        case_errors=case_errors,
    )
