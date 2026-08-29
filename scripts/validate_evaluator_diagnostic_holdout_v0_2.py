#!/usr/bin/env python3
"""Validate the Protocol v0.2 confirmatory holdout dataset + coupling metadata.

Validates ONLY the mechanical contract:

* holdout dataset: 24 pairs, 8 families x 3, HOLDOUT-{A..H}-{NN} ids, input
  validity, Layer-0 validity of reference/degraded plans, unknown-field
  rejection, reference != degraded, expected_flags frozen enum, no hardcoded
  target_dimensions, no id-space/content collision with the development dataset,
  and development dataset SHA-256 unchanged;
* metadata: coupling matrix partitions are pairwise disjoint and complete.

Does NOT call any API and does NOT run the Evaluator.

Usage:
    .venv/bin/python scripts/validate_evaluator_diagnostic_holdout_v0_2.py

Exit code 0 only if every check passes.
"""

from __future__ import annotations

import sys

from teachintent.evaluator_diagnostic import (
    HOLDOUT_DATASET_PATH,
    PROTOCOL_METADATA_PATH,
    validate_holdout_dataset,
    validate_protocol_metadata,
)


def main(argv: list[str]) -> int:
    holdout_report = validate_holdout_dataset()
    metadata_report = validate_protocol_metadata()

    print("=== Holdout dataset ===")
    print(f"Dataset: {HOLDOUT_DATASET_PATH}")
    print(f"Parsed pair count:        {holdout_report.parsed_count}")
    print(f"Input pass count:         {holdout_report.input_pass_count} / {holdout_report.parsed_count}")
    print(
        f"Reference plan pass:      {holdout_report.reference_pass_count} / {holdout_report.parsed_count}"
    )
    print(
        f"Degraded plan pass:       {holdout_report.degraded_pass_count} / {holdout_report.parsed_count}"
    )
    print()
    print("Dataset-level checks:")
    for name, detail in holdout_report.dataset_checks.items():
        status = "PASS" if detail == "" else "FAIL"
        line = f"  {name:.<40s} {status}"
        if detail:
            line += f"  {detail}"
        print(line)
    if holdout_report.case_errors:
        print()
        print(f"Pair-specific errors ({len(holdout_report.case_errors)}):")
        for err in holdout_report.case_errors:
            pid = err.pair_id or "?"
            print(f"  [{err.stage}] {pid}: {err.message}")

    print()
    print("=== Protocol v0.2 metadata ===")
    print(f"Metadata: {PROTOCOL_METADATA_PATH}")
    for name, detail in metadata_report.checks.items():
        status = "PASS" if detail == "" else "FAIL"
        line = f"  {name:.<40s} {status}"
        if detail:
            line += f"  {detail}"
        print(line)
    if metadata_report.case_errors:
        print()
        print("Metadata errors:")
        for err in metadata_report.case_errors:
            print(f"  - {err}")

    print()
    ok = holdout_report.all_passed and metadata_report.all_passed
    if ok:
        print("RESULT: ALL CHECKS PASSED")
        return 0
    print("RESULT: VALIDATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
