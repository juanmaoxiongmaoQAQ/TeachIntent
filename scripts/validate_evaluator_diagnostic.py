#!/usr/bin/env python3
"""Validate the frozen TeachIntent Evaluator diagnostic pairs dataset.

Validates ONLY the mechanical contract: 24 pairs, 8 families x 3, unique
pair_ids, input validity, Layer-0 validity of reference/degraded plans,
frozen dimension/flag enums, unknown-field rejection, and reference !=
degraded. Does NOT call any API and does NOT judge pedagogical reasonableness.

Usage:
    .venv/bin/python scripts/validate_evaluator_diagnostic.py            # default dataset
    .venv/bin/python scripts/validate_evaluator_diagnostic.py <path>     # explicit dataset

Exit code 0 only if every check passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_DATASET_PATH,
    validate_diagnostic_dataset,
)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DIAGNOSTIC_DATASET_PATH
    if not path.exists():
        print(f"ERROR: dataset file not found: {path}")
        return 2

    report = validate_diagnostic_dataset(path)

    print(f"Dataset: {path}")
    print(f"Parsed pair count:        {report.parsed_count}")
    print(f"Input pass count:         {report.input_pass_count} / {report.parsed_count}")
    print(
        f"Reference plan pass:      {report.reference_pass_count} / {report.parsed_count}"
    )
    print(
        f"Degraded plan pass:       {report.degraded_pass_count} / {report.parsed_count}"
    )
    print()
    print("Dataset-level checks:")
    for name, detail in report.dataset_checks.items():
        status = "PASS" if detail == "" else "FAIL"
        line = f"  {name:.<28s} {status}"
        if detail:
            line += f"  {detail}"
        print(line)

    if report.case_errors:
        print()
        print(f"Pair-specific errors ({len(report.case_errors)}):")
        for err in report.case_errors:
            pid = err.pair_id or "?"
            print(f"  [{err.stage}] {pid}: {err.message}")

    print()
    if report.all_passed:
        print("RESULT: ALL CHECKS PASSED")
        return 0
    print("RESULT: VALIDATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
