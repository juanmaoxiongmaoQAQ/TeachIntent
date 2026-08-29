#!/usr/bin/env python3
"""TeachIntent Evaluator Diagnostic Protocol v0.2 — confirmatory runner CLI.

Plans, (optionally) executes, aggregates, and persists the frozen confirmatory
experiment:

    24 holdout pairs x 2 variants x 3 repeats = 144 Evaluator calls

Frozen Judge condition (never read from env — hardcoded):
    provider:                openrouter
    model (requested):       qwen/qwen3.5-plus-20260420
    base URL:                https://openrouter.ai/api/v1
    temperature:             0
    structured_output:       false
    retry:                   false
    self_repair:             false
    evaluator_version:       v0.1
    judge_prompt_version:    v0.1

Usage:
    # Validate dataset/protocol hashes + config + 144-call plan (no API call).
    .venv/bin/python scripts/run_evaluator_diagnostic_confirmatory_v0_2.py --dry-run

    # Real confirmatory run (requires OPENROUTER_API_KEY in the environment).
    .venv/bin/python scripts/run_evaluator_diagnostic_confirmatory_v0_2.py \
        --output-dir results/evaluator_diagnostic_confirmatory/<run_id>

The API key is NEVER printed, logged, or written to any artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teachintent.evaluator_diagnostic import (
    CONFIRMATORY_DATASET_PATH,
    CONFIRMATORY_DATASET_SHA256,
    EXPECTED_CALLS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    aggregate,
    build_confirmatory_judge,
    prepare_confirmatory_run,
    execute_confirmatory_run,
    write_artifacts,
)

RESULTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "evaluator_diagnostic_confirmatory"
)


def _print_dry_run(run) -> None:
    print("=== Protocol v0.2 Confirmatory Dry-Run ===")
    print(f"run_id:                 {run.run_id}")
    print(f"started_at:             {run.started_at}")
    print(f"dataset:                {run.dataset_path}")
    print(f"dataset_sha256:         {run.dataset_sha256}")
    print(f"  frozen SHA match:     {run.integrity.dataset_sha_match}")
    print(f"  pair count (24):      {run.integrity.pair_count_match} ({len(run.pairs)} pairs)")
    print(f"  8 families x 3:       {run.integrity.family_distribution_match}")
    print(f"  freeze status Frozen: {run.integrity.freeze_status_frozen}")
    print(f"protocol_version:       v0.2")
    print(f"protocol_metadata_sha256: {run.protocol_metadata_sha256}")
    print(f"protocol_document_sha256: {run.protocol_document_sha256}")
    print(f"judge_provider:         {FROZEN_JUDGE_PROVIDER}")
    print(f"judge_model_requested:  {FROZEN_JUDGE_MODEL_REQUESTED}")
    print(f"temperature:            0")
    print(f"structured_output:      false")
    print(f"retry_enabled:          false")
    print(f"self_repair_enabled:    false")
    print(f"expected calls:         {EXPECTED_CALLS}")
    print(f"  pairs: {len(run.pairs)} x 2 variants x {run.repeats} repeats = "
          f"{len(run.pairs) * 2 * run.repeats} calls")
    print()
    print("No Judge API call was made (dry-run).")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=CONFIRMATORY_DATASET_PATH)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate + plan only; never call the Judge")
    args = parser.parse_args(argv)

    if args.repeats != 3:
        # Frozen Protocol v0.2 fixes the confirmatory design at 24 pairs x 2
        # variants x 3 repeats = 144 calls. Any other repeat count would run a
        # non-frozen experiment, so we fail fast instead of proceeding.
        parser.error(
            "--repeats must be exactly 3: frozen Protocol v0.2 fixes the "
            "confirmatory design at 24 pairs x 2 variants x 3 repeats = 144 calls"
        )

    # Prepare (integrity + metadata + plan). Fails fast on any frozen violation.
    try:
        run = prepare_confirmatory_run(args.dataset, repeats=args.repeats)
    except Exception as exc:  # noqa: BLE001 — report and stop before any call
        print(f"ERROR: pre-flight failed: {exc}")
        return 2

    judge = None if args.dry_run else build_confirmatory_judge()
    if not args.dry_run and judge is None:
        print("NOTE: OPENROUTER_API_KEY not set; falling back to dry-run (no API call).")

    if judge is not None:
        # Real confirmatory execution.
        execute_confirmatory_run(run, judge)
        agg = aggregate(run)
        out_dir = args.output_dir or (RESULTS_ROOT / run.run_id)
        write_artifacts(run, out_dir, agg=agg)
        print(f"Completed: {agg['operational'].successful} successful / "
              f"{agg['operational'].failed} failed / {EXPECTED_CALLS} expected")
        print(f"Semantic Validation: {agg['semantic'].verdict}")
        print(f"Artifacts: {out_dir}")
        return 0

    # Dry-run.
    _print_dry_run(run)
    if args.output_dir is not None:
        write_artifacts(run, args.output_dir, agg=None)
        print(f"Dry-run manifest written to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
