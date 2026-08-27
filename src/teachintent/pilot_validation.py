"""Structural validation for the frozen TeachIntent pilot datasets.

Supports two frozen blocks with a shared case-level pipeline and block-specific
dataset-level validation:

* Block A — ``controlled_contrast``
  (``cases/pilot/blocks/block_a_controlled_contrast.jsonl``);
* Block B — ``cross_domain_generalization``
  (``cases/pilot/blocks/block_b_cross_domain_generalization.jsonl``).

Shared case-level pipeline (identical for both blocks):

    json_parse -> wrapper_structure -> json_schema -> pydantic

``wrapper_structure`` is block-aware: Block A expects ``tags`` to contain
exactly ``{delivery_need, contrast_group}``; Block B expects exactly
``{delivery_need}`` (``contrast_group`` must NOT appear).

Dataset-level validation is dispatched per block:
``_shared_dataset_checks`` carries the common invariants; ``_block_a_dataset_checks``
and ``_block_b_dataset_checks`` carry the block-specific design invariants.
The block is auto-detected from the first parsed case's ``block`` field unless
passed explicitly via ``expected_block``.

Reuses the frozen runtime contract validators
(``teachintent.validators.iter_input_errors`` and
``teachintent.models.TeachIntentInput``) to validate ONLY ``case["input"]`` per
case. Experiment metadata is never passed into the runtime validators.

This module does NOT call Hy3 and requires no API credentials.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .models import TeachIntentInput
from .validators import iter_input_errors

__all__ = [
    "CaseError",
    "ValidationReport",
    "BLOCK_A",
    "BLOCK_B",
    "BLOCK_C",
    "PILOT_DATASET_PATH",
    "BLOCK_B_DATASET_PATH",
    "BLOCK_C_DATASET_PATH",
    "EXPECTED_CASE_COUNT",
    "EXPECTED_TOP_FIELDS",
    "EXPECTED_TAGS_FIELDS",
    "BLOCK_TAGS_FIELDS",
    "BLOCK_CASE_COUNTS",
    "SIX_INTENTS",
    "DELIVERY_NEEDS",
    "BLOCK_B_SUBJECTS",
    "BLOCK_B_LEARNER_LEVELS",
    "BLOCK_B_DELIVERY_NEED_DISTRIBUTION",
    "BLOCK_C_SUBJECTS",
    "BLOCK_C_LEARNER_LEVELS",
    "BLOCK_C_DELIVERY_NEED_DISTRIBUTION",
    "validate_pilot_cases",
]

# ---------------------------------------------------------------------------
# Block identifiers and dataset paths.
# ---------------------------------------------------------------------------
BLOCK_A = "controlled_contrast"
BLOCK_B = "cross_domain_generalization"
BLOCK_C = "hard_adversarial"

_BLOCKS_DIR = Path(__file__).resolve().parents[2] / "cases" / "pilot" / "blocks"
PILOT_DATASET_PATH = _BLOCKS_DIR / "block_a_controlled_contrast.jsonl"
BLOCK_B_DATASET_PATH = _BLOCKS_DIR / "block_b_cross_domain_generalization.jsonl"
BLOCK_C_DATASET_PATH = _BLOCKS_DIR / "block_c_hard_adversarial.jsonl"

# ---------------------------------------------------------------------------
# Shared constants (all blocks).
# ---------------------------------------------------------------------------
EXPECTED_CASE_COUNT = 12  # default; per-block overrides in BLOCK_CASE_COUNTS
EXPECTED_TOP_FIELDS = (
    "case_id",
    "block",
    "difficulty",
    "tags",
    "input",
    "design_expectations",
)

# Per-block expected case counts.
BLOCK_CASE_COUNTS: dict[str, int] = {
    BLOCK_A: 12,
    BLOCK_B: 12,
    BLOCK_C: 6,
}

# Per-block expected difficulty.
BLOCK_EXPECTED_DIFFICULTY: dict[str, str] = {
    BLOCK_A: "standard",
    BLOCK_B: "standard",
    BLOCK_C: "hard",
}

# Per-block expected count for each of the six intents.
BLOCK_INTENT_EXPECTED_COUNT: dict[str, int] = {
    BLOCK_A: 2,
    BLOCK_B: 2,
    BLOCK_C: 1,
}

# Block-aware expected tags fields (wrapper structure).
BLOCK_TAGS_FIELDS: dict[str, tuple[str, ...]] = {
    BLOCK_A: ("delivery_need", "contrast_group"),
    BLOCK_B: ("delivery_need",),
    BLOCK_C: ("delivery_need",),
}
# Backward-compatible alias for the Block A tags fields.
EXPECTED_TAGS_FIELDS = BLOCK_TAGS_FIELDS[BLOCK_A]

SIX_INTENTS = (
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
)
DELIVERY_NEEDS = ("low", "medium", "high")
EXPECTED_DIFFICULTY = "standard"
EXPECTED_SCHEMA_VERSION = "1.0.0-rc.2"
EXPECTED_OUTPUT_LANGUAGE = "zh-CN"

# ---------------------------------------------------------------------------
# Block B constants (cross_domain_generalization design).
# ---------------------------------------------------------------------------
BLOCK_B_SUBJECTS = (
    "mathematics",
    "english",
    "physics",
    "chemistry",
    "biology",
    "chinese",
)
BLOCK_B_LEARNER_LEVELS = (
    "elementary_school",
    "middle_school",
    "high_school",
)
BLOCK_B_LEARNER_UTTERANCE_COUNT = 10
BLOCK_B_AFFECTIVE_STATE_COUNT = 3
BLOCK_B_DELIVERY_NEED_DISTRIBUTION = {"low": 7, "medium": 4, "high": 1}
BLOCK_B_INTENT_ABBREVIATIONS = {
    "elicitation": "ELI",
    "scaffolding": "SCA",
    "explanation": "EXP",
    "corrective_feedback": "COR",
    "supportive_feedback": "SUP",
    "extension": "EXT",
}
# Shared alias (same mapping used by Block C case_id_format check).
INTENT_ABBREVIATIONS = BLOCK_B_INTENT_ABBREVIATIONS
BLOCK_B_CASE_ID_RE = re.compile(r"^PILOT-B-([A-Z]{3})-(\d{2})$")

# ---------------------------------------------------------------------------
# Block C constants (hard_adversarial design).
# ---------------------------------------------------------------------------
BLOCK_C_SUBJECTS = (
    "mathematics",
    "physics",
    "english",
    "chemistry",
    "chinese",
    "biology",
)
BLOCK_C_LEARNER_LEVELS = (
    "middle_school",
    "high_school",
)
BLOCK_C_DELIVERY_NEED_DISTRIBUTION = {"low": 3, "medium": 0, "high": 3}
BLOCK_C_CASE_ID_RE = re.compile(r"^PILOT-C-([A-Z]{3})-(\d{2})$")


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
    # The block this dataset was validated against (explicit or auto-detected).
    block: str | None = None

    @property
    def all_passed(self) -> bool:
        return (
            not self.case_errors
            and all(v == "" for v in self.dataset_checks.values())
        )


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Dataset-level checks — shared (all blocks).
# ---------------------------------------------------------------------------
def _shared_dataset_checks(
    valid_cases: list[dict],
    expected_block: str | None,
    expected_case_count: int,
    expected_difficulty: str,
    expected_intent_count: int,
) -> dict[str, str]:
    checks: dict[str, str] = {}

    # case count (per-block expected)
    if len(valid_cases) != expected_case_count:
        checks["case_count"] = (
            f"expected {expected_case_count} valid cases, got {len(valid_cases)}"
        )
    else:
        checks["case_count"] = ""

    # unique case ids
    case_ids = [c["case_id"] for c in valid_cases]
    id_counts = Counter(case_ids)
    duplicates = sorted(cid for cid, n in id_counts.items() if n > 1)
    checks["unique_case_ids"] = (
        f"duplicate case_id values: {duplicates}" if duplicates else ""
    )

    # block value
    bad_blocks = sorted(
        {c["block"] for c in valid_cases if c["block"] != expected_block}
    )
    checks["block_value"] = (
        f"unexpected block value(s): {bad_blocks}" if bad_blocks else ""
    )
    if expected_block not in BLOCK_TAGS_FIELDS:
        checks["block_dispatch"] = (
            f"unknown or undetectable block {expected_block!r}; "
            "block-specific checks were not run"
        )

    # difficulty value
    bad_difficulty = sorted(
        {c["difficulty"] for c in valid_cases if c["difficulty"] != expected_difficulty}
    )
    checks["difficulty_value"] = (
        f"unexpected difficulty value(s): {bad_difficulty}" if bad_difficulty else ""
    )

    # schema_version
    bad_versions = sorted(
        {
            c["input"]["schema_version"]
            for c in valid_cases
            if c["input"].get("schema_version") != EXPECTED_SCHEMA_VERSION
        }
    )
    checks["schema_version"] = (
        f"unexpected schema_version value(s): {bad_versions}" if bad_versions else ""
    )

    # output_language
    bad_langs = sorted(
        {
            c["input"]["output_language"]
            for c in valid_cases
            if c["input"].get("output_language") != EXPECTED_OUTPUT_LANGUAGE
        }
    )
    checks["output_language"] = (
        f"unexpected output_language value(s): {bad_langs}" if bad_langs else ""
    )

    # each of the six intents occurs the expected number of times
    intent_counts = Counter(
        c["input"]["pedagogical_intent"]["primary"] for c in valid_cases
    )
    intent_problems = []
    for intent in SIX_INTENTS:
        n = intent_counts.get(intent, 0)
        if n != expected_intent_count:
            intent_problems.append(f"{intent}={n}")
    extra_intents = sorted(set(intent_counts) - set(SIX_INTENTS))
    for intent in extra_intents:
        intent_problems.append(f"{intent}={intent_counts[intent]} (unexpected)")
    checks["intent_counts"] = (
        f"intent counts not exactly {expected_intent_count} each: {intent_problems}"
        if intent_problems
        else ""
    )

    # delivery_need in {low, medium, high}
    bad_needs = []
    for c in valid_cases:
        need = c["tags"].get("delivery_need")
        if need not in DELIVERY_NEEDS:
            bad_needs.append(f"{c['case_id']}={need!r}")
    checks["delivery_need_values"] = (
        f"invalid delivery_need value(s): {bad_needs}" if bad_needs else ""
    )

    # design_expectations.must / must_not non-empty lists of non-empty strings
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
    checks["design_expectations"] = (
        f"malformed design_expectations field(s): {bad_expectations}"
        if bad_expectations
        else ""
    )

    return checks


# ---------------------------------------------------------------------------
# Dataset-level checks — Block A (controlled_contrast). Preserved exactly.
# ---------------------------------------------------------------------------
def _block_a_dataset_checks(valid_cases: list[dict]) -> dict[str, str]:
    checks: dict[str, str] = {}

    # exactly six anchor_01 and six anchor_02
    anchor_counts = Counter(c["tags"]["contrast_group"] for c in valid_cases)
    anchor_problems = []
    if anchor_counts.get("anchor_01", 0) != 6:
        anchor_problems.append(f"anchor_01={anchor_counts.get('anchor_01', 0)}")
    if anchor_counts.get("anchor_02", 0) != 6:
        anchor_problems.append(f"anchor_02={anchor_counts.get('anchor_02', 0)}")
    extra_anchors = sorted(set(anchor_counts) - {"anchor_01", "anchor_02"})
    for anchor in extra_anchors:
        anchor_problems.append(f"{anchor}={anchor_counts[anchor]} (unexpected)")
    checks["contrast_group_counts"] = (
        f"contrast_group counts not 6/6: {anchor_problems}"
        if anchor_problems
        else ""
    )

    # case_id suffix maps to matching contrast_group
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
    checks["case_id_anchor_mapping"] = (
        f"case_id/anchor mismatches: {mismatches}" if mismatches else ""
    )

    return checks


# ---------------------------------------------------------------------------
# Dataset-level checks — Block B (cross_domain_generalization).
# ---------------------------------------------------------------------------
def _block_b_dataset_checks(valid_cases: list[dict]) -> dict[str, str]:
    checks: dict[str, str] = {}

    # case_id format: PILOT-B-{INTENT}-{NN}, consistent with the runtime intent
    problems: list[str] = []
    for c in valid_cases:
        case_id = c["case_id"]
        match = BLOCK_B_CASE_ID_RE.match(case_id)
        if match is None:
            problems.append(f"{case_id} (format)")
            continue
        abbrev = match.group(1)
        intent = c["input"]["pedagogical_intent"]["primary"]
        expected_abbrev = BLOCK_B_INTENT_ABBREVIATIONS.get(intent)
        if expected_abbrev is None or abbrev != expected_abbrev:
            problems.append(f"{case_id} (intent mismatch: {intent})")
    checks["case_id_format"] = (
        f"case_id format/intent problems: {problems}" if problems else ""
    )

    # all six frozen subject domains represented
    subjects = {
        c["input"]["instructional_content"]["subject"] for c in valid_cases
    }
    missing_subjects = sorted(set(BLOCK_B_SUBJECTS) - subjects)
    checks["subject_coverage"] = (
        f"missing subject domain(s): {missing_subjects}"
        if missing_subjects
        else ""
    )

    # all three learner levels represented
    levels = {c["input"]["learner"]["level"] for c in valid_cases}
    missing_levels = sorted(set(BLOCK_B_LEARNER_LEVELS) - levels)
    checks["learner_level_coverage"] = (
        f"missing learner level(s): {missing_levels}" if missing_levels else ""
    )

    # learner_utterance present in exactly 10/12 cases
    utterance_count = sum(
        1
        for c in valid_cases
        if "learner_utterance" in c["input"]["pedagogical_context"]
    )
    checks["learner_utterance_count"] = (
        ""
        if utterance_count == BLOCK_B_LEARNER_UTTERANCE_COUNT
        else (
            f"expected learner_utterance in exactly "
            f"{BLOCK_B_LEARNER_UTTERANCE_COUNT}/{EXPECTED_CASE_COUNT} cases, "
            f"got {utterance_count}"
        )
    )

    # affective_state present in exactly 3/12 cases
    affective_count = sum(
        1 for c in valid_cases if "affective_state" in c["input"]["learner"]
    )
    checks["affective_state_count"] = (
        ""
        if affective_count == BLOCK_B_AFFECTIVE_STATE_COUNT
        else (
            f"expected affective_state in exactly "
            f"{BLOCK_B_AFFECTIVE_STATE_COUNT}/{EXPECTED_CASE_COUNT} cases, "
            f"got {affective_count}"
        )
    )

    # frozen delivery_need distribution: low=7, medium=4, high=1
    dist = Counter(c["tags"]["delivery_need"] for c in valid_cases)
    dist_problems = []
    for need, expected_n in sorted(BLOCK_B_DELIVERY_NEED_DISTRIBUTION.items()):
        actual_n = dist.get(need, 0)
        if actual_n != expected_n:
            dist_problems.append(f"{need}={actual_n} (expected {expected_n})")
    extra_needs = sorted(set(dist) - set(BLOCK_B_DELIVERY_NEED_DISTRIBUTION))
    for need in extra_needs:
        dist_problems.append(f"{need}={dist[need]} (unexpected)")
    checks["delivery_need_distribution"] = (
        f"delivery_need distribution mismatch: {dist_problems}"
        if dist_problems
        else ""
    )

    return checks


# ---------------------------------------------------------------------------
# Dataset-level checks — Block C (hard_adversarial).
# ---------------------------------------------------------------------------
def _block_c_dataset_checks(valid_cases: list[dict]) -> dict[str, str]:
    checks: dict[str, str] = {}

    # case_id format: PILOT-C-{INTENT}-{NN}, consistent with the runtime intent
    problems: list[str] = []
    for c in valid_cases:
        case_id = c["case_id"]
        match = BLOCK_C_CASE_ID_RE.match(case_id)
        if match is None:
            problems.append(f"{case_id} (format)")
            continue
        abbrev = match.group(1)
        intent = c["input"]["pedagogical_intent"]["primary"]
        expected_abbrev = INTENT_ABBREVIATIONS.get(intent)
        if expected_abbrev is None or abbrev != expected_abbrev:
            problems.append(f"{case_id} (intent mismatch: {intent})")
    checks["case_id_format"] = (
        f"case_id format/intent problems: {problems}" if problems else ""
    )

    # all six frozen subjects represented exactly once
    subject_counts = Counter(
        c["input"]["instructional_content"]["subject"] for c in valid_cases
    )
    subject_problems: list[str] = []
    for subj in BLOCK_C_SUBJECTS:
        n = subject_counts.get(subj, 0)
        if n != 1:
            subject_problems.append(f"{subj}={n} (expected 1)")
    extra_subjects = sorted(set(subject_counts) - set(BLOCK_C_SUBJECTS))
    for subj in extra_subjects:
        subject_problems.append(f"{subj}={subject_counts[subj]} (unexpected)")
    checks["subject_coverage"] = (
        f"subject coverage problems: {subject_problems}"
        if subject_problems
        else ""
    )

    # learner levels are exactly middle_school and high_school
    levels = {c["input"]["learner"]["level"] for c in valid_cases}
    expected_levels = set(BLOCK_C_LEARNER_LEVELS)
    level_problems: list[str] = []
    missing_levels = sorted(expected_levels - levels)
    extra_levels = sorted(levels - expected_levels)
    if missing_levels:
        level_problems.append(f"missing: {missing_levels}")
    if extra_levels:
        level_problems.append(f"unexpected: {extra_levels}")
    checks["learner_level_coverage"] = (
        f"learner level problems: {level_problems}" if level_problems else ""
    )

    # frozen delivery_need distribution: low=3, medium=0, high=3
    dist = Counter(c["tags"]["delivery_need"] for c in valid_cases)
    dist_problems: list[str] = []
    for need, expected_n in sorted(BLOCK_C_DELIVERY_NEED_DISTRIBUTION.items()):
        actual_n = dist.get(need, 0)
        if actual_n != expected_n:
            dist_problems.append(f"{need}={actual_n} (expected {expected_n})")
    extra_needs = sorted(set(dist) - set(BLOCK_C_DELIVERY_NEED_DISTRIBUTION))
    for need in extra_needs:
        dist_problems.append(f"{need}={dist[need]} (unexpected)")
    checks["delivery_need_distribution"] = (
        f"delivery_need distribution mismatch: {dist_problems}"
        if dist_problems
        else ""
    )

    return checks


_DATASET_CHECK_DISPATCH = {
    BLOCK_A: _block_a_dataset_checks,
    BLOCK_B: _block_b_dataset_checks,
    BLOCK_C: _block_c_dataset_checks,
}


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------
def validate_pilot_cases(
    path: Path,
    expected_block: str | None = None,
) -> ValidationReport:
    """Validate a pilot dataset at *path*.

    The block is auto-detected from the first parsed case's ``block`` field
    unless ``expected_block`` is passed explicitly. Returns a
    :class:`ValidationReport`. Does not raise on validation failures; only
    raises on I/O errors (file not found, etc.).
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

    # ---- Stage 1.5: detect the block (explicit param or first case's value) ----
    if expected_block is None:
        for _, case in cases:
            block_value = case.get("block")
            if isinstance(block_value, str):
                expected_block = block_value
                break

    # ---- Stage 2: wrapper structure (top-level + block-aware tags fields) ----
    # The experiment wrapper must carry exactly the expected top-level fields
    # and a tags sub-object with exactly the block-specific expected fields.
    # Missing AND unexpected fields are rejected at this level, before any
    # runtime validation, so experiment metadata is never treated as runtime
    # input.
    tags_expected = BLOCK_TAGS_FIELDS.get(expected_block)  # None if unknown block
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

        # tags sub-object: must be a dict with exactly the block-specific fields.
        if "tags" in case:
            tags = case["tags"]
            if not isinstance(tags, dict):
                issues.append("tags is not an object")
            elif tags_expected is not None:
                tags_keys = set(tags.keys())
                missing_tags = [f for f in tags_expected if f not in tags_keys]
                unexpected_tags = sorted(tags_keys - set(tags_expected))
                if missing_tags:
                    issues.append(f"missing tags field(s): {missing_tags}")
                if unexpected_tags:
                    issues.append(f"unexpected tags field(s): {unexpected_tags}")
            # else: unknown block — tags field-set check deferred to the
            # block_dispatch dataset check.

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

    # ---- Stage 4: dataset-level checks (shared + block-specific dispatch) ----
    valid_cases = [case for _, _, case in runtime_inputs]

    expected_case_count = BLOCK_CASE_COUNTS.get(expected_block, EXPECTED_CASE_COUNT)
    expected_difficulty = BLOCK_EXPECTED_DIFFICULTY.get(
        expected_block, EXPECTED_DIFFICULTY
    )
    expected_intent_count = BLOCK_INTENT_EXPECTED_COUNT.get(expected_block, 2)
    dataset_checks = _shared_dataset_checks(
        valid_cases,
        expected_block,
        expected_case_count,
        expected_difficulty,
        expected_intent_count,
    )
    block_check_fn = _DATASET_CHECK_DISPATCH.get(expected_block)
    if block_check_fn is not None:
        dataset_checks.update(block_check_fn(valid_cases))

    return ValidationReport(
        parsed_count=parsed_count,
        json_schema_pass_count=json_schema_pass,
        pydantic_pass_count=pydantic_pass,
        dataset_checks=dataset_checks,
        case_errors=case_errors,
        block=expected_block,
    )
