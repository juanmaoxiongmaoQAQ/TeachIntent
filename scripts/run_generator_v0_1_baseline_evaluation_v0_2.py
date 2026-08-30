#!/usr/bin/env python3
"""TeachIntent Generator v0.1 Baseline Evaluation — runner CLI (Protocol v0.2).

Protocol v0.2 (``docs/generator_v0.1_evaluation_protocol_v0.2.md``,
Status: **Frozen**, frozen 2026-08-30) is an **operational revision** of v0.1.
It keeps the semantic design frozen and adds an outer attempt policy:

    30 cases x 3 semantic repeats  =  90 planned semantic evaluations
    each semantic repeat           <= 3 physical attempts (270 worst case)

A physical attempt is retried **only** when it failed to form a legal Evaluator
artifact. The moment a legal artifact exists the semantic repeat is closed,
regardless of how low the scores are or how many critical flags were raised.

Retryable:   judge_api_error, judge_response_parse_error,
             judge_output_schema_error, evidence_source_error,
             evidence_grounding_error
Fatal:       setup_* errors, internal_evaluator_error, Layer-0 gate failures

Evaluator v0.1 internal retry stays DISABLED
(``evaluator_retry_enabled = false``); the runner's attempt retry is a separate,
outer policy (``baseline_attempt_retry_enabled = true``).

The Generator v0.1 outputs are REUSED AS-IS from three frozen Pilot runs:

    Block A (controlled_contrast)         20260827-002543   12 cases
    Block B (cross_domain_generalization) 20260827-051547   12 cases
    Block C (hard_adversarial)            20260827-074602    6 cases

Frozen Judge condition (imported from the frozen protocol constants, never read
from env):
    provider:                openrouter
    model (requested):       qwen/qwen3.5-plus-20260420
    temperature:             0
    structured_output:       false
    self_repair:             false
    evaluator_version:       v0.1
    judge_prompt_version:    v0.1

Usage:
    # Offline pre-flight: population integrity + fingerprint + plan.
    # Needs NO API key and makes no Judge call.
    .venv/bin/python scripts/run_generator_v0_1_baseline_evaluation_v0_2.py \
        --dry-run

    # Real run (requires OPENROUTER_API_KEY in the environment).
    # Without the key the run aborts with exit code 2 BEFORE the first attempt,
    # so a missing credential can never degrade into rows of judge_api_error.
    .venv/bin/python scripts/run_generator_v0_1_baseline_evaluation_v0_2.py \
        --output-dir results/generator_v0_1_baseline_evaluation_v0_2/<run_id>

This produces a DESCRIPTIVE baseline, not a Generator PASS/FAIL verdict.

Protocol v0.1 Run 1 (``20260830T063227Z``, 58/90, 19/30 eligible) is preserved
as a permanent historical record and is written under a DIFFERENT directory
(``results/generator_v0_1_baseline_evaluation/``). This runner cannot reach it.

The API key is NEVER printed, logged, or written to any artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teachintent.generator_evaluation.baseline_v0_2 import (
    BASELINE_ATTEMPT_RETRY_ENABLED,
    CASE_COUNT,
    EVALUATOR_RETRY_ENABLED,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
    NON_RETRYABLE_FAILURE_TYPES,
    PLANNED_SEMANTIC_REPEATS,
    PROTOCOL_STATUS,
    PROTOCOL_VERSION,
    REPEATS,
    RETRYABLE_FAILURE_TYPES,
    aggregate_v0_2,
    build_baseline_judge,
    execute_baseline_run_v2,
    prepare_baseline_run_v2,
    write_artifacts_v2,
)

# v0.2 results live in their own root so Protocol v0.1 Run 1 is structurally
# unreachable and can never be overwritten.
RESULTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "generator_v0_1_baseline_evaluation_v0_2"
)


def _print_dry_run(run) -> None:
    print("=== Generator v0.1 Baseline Evaluation (Protocol v0.2) — Dry-Run ===")
    print()
    print(f"Protocol version: {PROTOCOL_VERSION}")
    print(f"Protocol status: {PROTOCOL_STATUS}")
    # Recomputed from the protocol document on every run, so a frozen run can
    # never be attributed to a stale Draft-revision SHA.
    print(f"protocol_document_sha256 = {run.protocol_document_sha256}")
    print()
    print("source runs:")
    for src in run.source_runs:
        print(f"  {src['block']} = {src['run_id']}")
    print()
    counts = "/".join(str(src["actual_cases"]) for src in run.source_runs)
    print(f"A/B/C = {counts}")
    print(f"total cases = {len(run.cases)}")
    print()
    integrity = run.integrity
    print(f"unique case ids = {integrity.unique_case_ids}")
    print(f"restorable cases = {integrity.restorable_cases}/{integrity.total_cases}")
    print(f"prompt_versions = {integrity.prompt_versions}")
    print(f"generation outcomes = {integrity.generation_outcomes}")
    print()
    print(f"source_population_sha256 = {run.source_population_sha256}")
    print(
        "expected source_population_sha256 = "
        f"{run.source_population_sha256_expected}"
    )
    print(f"SHA match = {run.source_population_sha256_match}")
    print()
    print(f"Generator = {run.generator_version}")
    print(f"Prompt = {run.prompt_version}")
    print("Evaluator = v0.1")
    print(f"Judge = {FROZEN_JUDGE_MODEL_REQUESTED}")
    print(f"Judge provider = {FROZEN_JUDGE_PROVIDER}")
    print(f"temperature = 0 / structured_output = False / self_repair = False")
    print()
    print(f"semantic repeats per case = {run.semantic_repeats_per_case}")
    print(f"planned semantic repeats = {run.planned_semantic_repeats}")
    print(f"  {len(run.cases)} cases x {run.semantic_repeats_per_case} semantic "
          f"repeats = {run.planned_semantic_repeats}")
    print()
    print(f"max attempts per semantic repeat = "
          f"{run.max_attempts_per_semantic_repeat}")
    print(f"max possible physical attempts = {run.max_possible_physical_attempts}")
    print()
    print(f"baseline attempt retry = "
          f"{'enabled' if BASELINE_ATTEMPT_RETRY_ENABLED else 'disabled'}")
    print()
    print("retryable failure types:")
    for failure_type in RETRYABLE_FAILURE_TYPES:
        print(f"  - {failure_type}")
    print()
    print("non-retryable failure types:")
    for failure_type in NON_RETRYABLE_FAILURE_TYPES:
        print(f"  - {failure_type}")
    print()
    print(f"evaluator internal retry = "
          f"{'enabled' if EVALUATOR_RETRY_ENABLED else 'disabled'}")
    print()
    print("No Judge API call was made.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generator v0.1 baseline evaluation runner (Protocol v0.2)"
    )
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the canonical population + plan only; never call the Judge",
    )
    args = parser.parse_args(argv)

    if args.repeats != REPEATS:
        # The semantic design is frozen at 30 x 3 = 90 semantic repeats.
        parser.error(
            f"--repeats must be exactly {REPEATS}: the baseline design is fixed "
            f"at {CASE_COUNT} cases x {REPEATS} semantic repeats = "
            f"{PLANNED_SEMANTIC_REPEATS} planned semantic repeats"
        )
    if args.max_attempts != MAX_ATTEMPTS_PER_SEMANTIC_REPEAT:
        parser.error(
            "--max-attempts must be exactly "
            f"{MAX_ATTEMPTS_PER_SEMANTIC_REPEAT}: Protocol v0.2 freezes the "
            f"outer attempt policy at {MAX_ATTEMPTS_PER_SEMANTIC_REPEAT} "
            f"physical attempts per semantic repeat (attempt 4 is prohibited)"
        )

    # Prepare: load + verify the 30 canonical cases, plan the 90 semantic
    # repeats. Fails fast on any population integrity violation. No API call.
    try:
        run = prepare_baseline_run_v2(repeats=args.repeats)
    except Exception as exc:  # noqa: BLE001 — report and stop before any call
        print(f"ERROR: pre-flight failed: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        # Offline pre-flight only. No Judge is ever constructed in dry-run.
        _print_dry_run(run)
        if args.output_dir is not None:
            write_artifacts_v2(run, args.output_dir, agg=None)
            print(f"Dry-run manifest written to: {args.output_dir}")
        return 0

    # ---- Formal mode ----
    # Fail fast BEFORE any Judge is constructed and before the first physical
    # attempt: a missing key must never degrade into rows of judge_api_error.
    # Only the key's PRESENCE is checked — never its value, never printed.
    judge = build_baseline_judge()
    if judge is None:
        print(
            "ERROR: OPENROUTER_API_KEY is not set (or is empty) in the "
            "environment.\n"
            "       The formal Generator v0.1 baseline run (Protocol v0.2) "
            "requires the frozen Judge backend.\n"
            "       Aborting before any Judge call — no physical attempt was "
            "made and no result run was created.\n"
            "       Use --dry-run for the offline pre-flight, which needs no key.",
            file=sys.stderr,
        )
        return 2

    execute_baseline_run_v2(run, judge, max_attempts=args.max_attempts)
    agg = aggregate_v0_2(run)
    out_dir = args.output_dir or (RESULTS_ROOT / run.run_id)
    write_artifacts_v2(run, out_dir, agg=agg)

    global_metrics = agg["global"]
    ops = global_metrics["operational_attempt_metrics"]
    print(
        f"Completed: {ops['successful_semantic_repeats']} successful / "
        f"{ops['failed_semantic_repeats']} failed / "
        f"{PLANNED_SEMANTIC_REPEATS} planned semantic repeats"
    )
    print(
        f"Physical attempts: {ops['total_physical_attempts']} "
        f"(max possible {MAX_POSSIBLE_PHYSICAL_ATTEMPTS})"
    )
    print(
        f"First-attempt success rate: {ops['first_attempt_success_rate']} — "
        f"retry recovery rate: {ops['retry_recovery_rate']}"
    )
    print(f"Eligible cases: {global_metrics['eligible_case_count']}/{CASE_COUNT}")
    print(f"Overall score mean: {global_metrics['overall_score']['mean']}")
    print("Generator v0.1 Baseline Evaluation (descriptive; no PASS/FAIL).")
    print(f"Artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
