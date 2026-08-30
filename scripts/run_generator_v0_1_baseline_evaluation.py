#!/usr/bin/env python3
"""TeachIntent Generator v0.1 Baseline Evaluation — runner CLI.

Measures the 30 canonical Generator v0.1 Pilot outputs with the frozen,
already-validated Evaluator v0.1:

    30 cases x 3 repeats = 90 Evaluator calls

The Generator v0.1 outputs are REUSED AS-IS from three frozen Pilot runs:

    Block A (controlled_contrast)         20260827-002543   12 cases
    Block B (cross_domain_generalization) 20260827-051547   12 cases
    Block C (hard_adversarial)            20260827-074602    6 cases

Nothing is regenerated, replaced, cherry-picked, dropped, or repaired.

Frozen Judge condition (never read from env — imported from the frozen
protocol constants):
    provider:                openrouter
    model (requested):       qwen/qwen3.5-plus-20260420
    temperature:             0
    structured_output:       false
    retry:                   false
    self_repair:             false
    evaluator_version:       v0.1
    judge_prompt_version:    v0.1

Usage:
    # Offline pre-flight: population integrity + fingerprint + 90-call plan.
    # Needs NO API key and makes no Judge call.
    .venv/bin/python scripts/run_generator_v0_1_baseline_evaluation.py --dry-run

    # Real run (requires OPENROUTER_API_KEY in the environment).
    # Without the key the run aborts with exit code 2 BEFORE the first call,
    # so a missing credential can never degrade into 90 judge_api_error rows.
    .venv/bin/python scripts/run_generator_v0_1_baseline_evaluation.py \
        --output-dir results/generator_v0_1_baseline_evaluation/<run_id>

This produces a DESCRIPTIVE baseline, not a Generator PASS/FAIL verdict.

The API key is NEVER printed, logged, or written to any artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teachintent.generator_evaluation import (
    CASE_COUNT,
    EXPECTED_CALLS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    REPEATS,
    aggregate,
    build_baseline_judge,
    execute_baseline_run,
    prepare_baseline_run,
    write_artifacts,
)

RESULTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "generator_v0_1_baseline_evaluation"
)


def _print_dry_run(run) -> None:
    print("=== Generator v0.1 Baseline Evaluation — Dry-Run ===")
    print(f"run_id:                {run.run_id}")
    print(f"protocol_version:      {run.protocol_version} (status: {run.protocol_status})")
    print()
    print("Generator v0.1 canonical runs:")
    for src in run.source_runs:
        print(f"  {src['block']} = {src['run_id']}   ({src['block_name']})")
    print()
    print("case counts:")
    for src in run.source_runs:
        print(f"  {src['block']} = {src['actual_cases']}")
    print(f"  total = {len(run.cases)}")
    print()
    integrity = run.integrity
    print(f"unique case ids = {integrity.unique_case_ids}")
    print(f"restorable cases = {integrity.restorable_cases}/{integrity.total_cases}")
    print(f"prompt_versions = {integrity.prompt_versions}")
    print(f"generation outcomes = {integrity.generation_outcomes}")
    print()
    print(f"source_population_sha256 = {run.source_population_sha256}")
    print(f"source_population_sha256 (expected) = {run.source_population_sha256_expected}")
    print(f"source_population_sha256 match = {run.source_population_sha256_match}")
    print()
    print(f"Generator version = {run.generator_version}")
    print(f"Generator version provenance = {run.generator_version_provenance}")
    print(f"Prompt version = {run.prompt_version}")
    print(f"Prompt version provenance = {run.prompt_version_provenance}")
    print()
    print("Evaluator version = v0.1")
    print(f"Judge model = {FROZEN_JUDGE_MODEL_REQUESTED}")
    print(f"Judge provider = {FROZEN_JUDGE_PROVIDER}")
    print()
    print(f"repeats = {run.repeats}")
    print(f"expected Judge calls = {run.planned_calls}")
    print(f"  {len(run.cases)} cases x {run.repeats} repeats = {run.planned_calls} calls")
    print()
    print("No Judge API call was made.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generator v0.1 baseline evaluation runner"
    )
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the canonical population + plan only; never call the Judge",
    )
    args = parser.parse_args(argv)

    if args.repeats != REPEATS:
        # The baseline design is fixed at 30 cases x 3 repeats = 90 calls.
        # Any other repeat count would run a different experiment, so we fail
        # fast instead of silently deviating.
        parser.error(
            f"--repeats must be exactly {REPEATS}: the baseline design is fixed "
            f"at {CASE_COUNT} cases x {REPEATS} repeats = {EXPECTED_CALLS} calls"
        )

    # Prepare: load + verify the 30 canonical cases, plan the 90 calls.
    # Fails fast on any population integrity violation. No API call.
    try:
        run = prepare_baseline_run(repeats=args.repeats)
    except Exception as exc:  # noqa: BLE001 — report and stop before any call
        print(f"ERROR: pre-flight failed: {exc}")
        return 2

    if args.dry_run:
        # Offline pre-flight only. No Judge is ever constructed in dry-run.
        _print_dry_run(run)
        if args.output_dir is not None:
            write_artifacts(run, args.output_dir, agg=None)
            print(f"Dry-run manifest written to: {args.output_dir}")
        return 0

    # ---- Formal mode ----
    # Fail fast BEFORE any Judge is constructed and before the first call: a
    # missing key must never degrade into 90 judge_api_error records.
    # The key's value is never read, printed, or stored — only its presence.
    judge = build_baseline_judge()
    if judge is None:
        print(
            "ERROR: OPENROUTER_API_KEY is not set (or is empty) in the "
            "environment.\n"
            "       The formal Generator v0.1 baseline run requires the frozen "
            "Judge backend.\n"
            "       Aborting before any Judge call — no evaluation was "
            "attempted.\n"
            "       Use --dry-run for the offline pre-flight, which needs no key.",
            file=sys.stderr,
        )
        return 2

    # Real baseline execution: 30 cases x 3 repeats = 90 calls.
    execute_baseline_run(run, judge)
    agg = aggregate(run)
    out_dir = args.output_dir or (RESULTS_ROOT / run.run_id)
    write_artifacts(run, out_dir, agg=agg)
    global_metrics = agg["global"]
    print(
        f"Completed: {global_metrics['successful_calls']} successful / "
        f"{global_metrics['failed_calls']} failed / {EXPECTED_CALLS} expected"
    )
    print(f"Eligible cases: {global_metrics['eligible_case_count']}/{CASE_COUNT}")
    print(f"Overall score mean: {global_metrics['overall_score']['mean']}")
    print("Generator v0.1 Baseline Evaluation (descriptive; no PASS/FAIL).")
    print(f"Artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
