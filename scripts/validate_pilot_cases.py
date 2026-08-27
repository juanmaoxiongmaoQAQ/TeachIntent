#!/usr/bin/env python3
"""Validate a frozen TeachIntent pilot dataset (Block A or Block B).

Validates ONLY ``case["input"]`` per case through the existing frozen runtime
contract (JSON Schema + Pydantic), then runs block-specific dataset-level
checks. The block is auto-detected from the dataset. Experiment metadata is
never treated as runtime input. Does not call Hy3 and requires no API
credentials.

Usage:
    .venv/bin/python scripts/validate_pilot_cases.py                        # Block A (default)
    .venv/bin/python scripts/validate_pilot_cases.py <path-to-jsonl>        # explicit dataset

Examples:
    .venv/bin/python scripts/validate_pilot_cases.py cases/pilot/blocks/block_a_controlled_contrast.jsonl
    .venv/bin/python scripts/validate_pilot_cases.py cases/pilot/blocks/block_b_cross_domain_generalization.jsonl

Exit code 0 only if every check passes; non-zero otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

from teachintent.pilot_validation import (
    BLOCK_B_DATASET_PATH,
    PILOT_DATASET_PATH,
    validate_pilot_cases,
)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else PILOT_DATASET_PATH
    if not path.exists():
        print(f"ERROR: dataset file not found: {path}")
        return 2

    report = validate_pilot_cases(path)

    print(f"Dataset: {path}")
    print(f"Block (detected):         {report.block}")
    print(f"Parsed case count:        {report.parsed_count}")
    print(
        f"JSON Schema pass count:   {report.json_schema_pass_count}"
        f" / {report.parsed_count}"
    )
    print(
        f"Pydantic pass count:      {report.pydantic_pass_count}"
        f" / {report.parsed_count}"
    )
    print()
    print("Dataset-level checks:")
    for name, detail in report.dataset_checks.items():
        status = "PASS" if detail == "" else "FAIL"
        line = f"  {name:.<40s} {status}"
        if detail:
            line += f"  {detail}"
        print(line)

    if report.case_errors:
        print()
        print(f"Case-specific errors ({len(report.case_errors)}):")
        for err in report.case_errors:
            cid = err.case_id or "?"
            print(
                f"  line {err.line_number} [{err.stage}] {cid}: {err.message}"
            )

    print()
    if report.all_passed:
        print("RESULT: ALL CHECKS PASSED")
        return 0
    print("RESULT: VALIDATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
