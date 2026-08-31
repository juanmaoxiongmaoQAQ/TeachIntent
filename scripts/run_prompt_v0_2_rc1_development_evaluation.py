#!/usr/bin/env python3
"""Prompt v0.2-rc.1 paired development evaluation — runner CLI.

Compares the FINISHED Generator v0.1 baseline (Prompt v0.1) against the
FINISHED Prompt v0.2-rc.1 candidate generation, using the SAME frozen
Evaluator v0.1 acquisition policy as Protocol v0.2
(``docs/generator_v0.1_evaluation_protocol_v0.2.md``, Status: **Frozen**).

Neither side is regenerated:

    v0.1 generation   three canonical Pilot runs (A/B/C = 12/12/6), reused
    v0.1 evaluation   baseline run 20260830T095934Z, reused READ-ONLY
    rc.1 generation   development run 20260831-052126, reused READ-ONLY
    rc.1 evaluation   NEW — the only Judge calls in this experiment

    30 candidate plans x 3 semantic repeats  =  90 planned semantic evaluations
    each semantic repeat                    <= 3 physical attempts (270 worst case)

Frozen Judge condition (identical on both sides; provider/base-url/model are
never read from the environment):

    evaluator_version:       v0.1
    judge_prompt_version:    v0.1
    judge provider:          openrouter
    judge model (requested): qwen/qwen3.5-plus-20260420
    temperature:             0
    structured_output:       false
    evaluator retry:         false
    self_repair:             false

The retryable taxonomy and the <= 3 physical-attempt policy are IMPORTED from
the frozen Protocol v0.2 implementation, not redesigned here.

Usage:

    # Offline pre-flight: both populations + cross-side identity + the plan.
    # No Judge is constructed and no API call is made.
    .venv/bin/python scripts/run_prompt_v0_2_rc1_development_evaluation.py \
        --dry-run

    # Formal run (requires OPENROUTER_API_KEY). Without the key the run aborts
    # with exit code 2 BEFORE the first attempt and before any result directory
    # is created.
    .venv/bin/python scripts/run_prompt_v0_2_rc1_development_evaluation.py \
        --execute

This produces DEVELOPMENT evidence, not held-out confirmatory evidence.
No PASS/FAIL threshold is computed.

The API key is never printed, logged, or written to any artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teachintent.generator_evaluation.baseline_v0_1 import (
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    build_baseline_judge,
)
from teachintent.prompt_development.development_evaluation import (
    CANDIDATE_GENERATION_RUN_ID,
    CASE_COUNT,
    MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
    PLANNED_SEMANTIC_REPEATS,
    RESULTS_ROOT,
    DevelopmentEvaluationError,
    case_pair_rows,
    execute_candidate_evaluation,
    prepare_development_evaluation,
    write_development_artifacts,
)

_USAGE = (
    "usage: run_prompt_v0_2_rc1_development_evaluation.py "
    "{--dry-run | --execute}\n"
    "  --dry-run   validate both populations, assert cross-side identity and\n"
    "              print the plan; never constructs a Judge, never calls the\n"
    "              API, never creates a result run.\n"
    "  --execute   run the 90 rc.1 semantic evaluations with the frozen Judge\n"
    "              and write the paired comparison artifacts.\n"
    "\n"
    "  Exactly one of --dry-run / --execute is required; neither or both is an\n"
    "  error. The v0.1 side is never regenerated and never re-evaluated."
)


def _print_dry_run(run) -> None:
    integrity = run.integrity
    print("=== Prompt v0.2-rc.1 Paired Development Evaluation — Dry-Run ===")
    print()
    print(f"baseline population = {len(run.baseline.case_rows)}")
    print(f"candidate population = {integrity.total_cases}")
    print(f"case IDs exact match = {integrity.case_ids_exact_match}")
    print()
    print(f"baseline evaluation run = {run.baseline.run_id}")
    print(f"candidate generation run = {CANDIDATE_GENERATION_RUN_ID}")
    print()
    print("Evaluator = v0.1")
    print(f"Judge = {FROZEN_JUDGE_MODEL_REQUESTED}")
    print(f"semantic repeats = {run.candidate_run.semantic_repeats_per_case}")
    print(
        "max physical attempts = "
        f"{run.candidate_run.max_attempts_per_semantic_repeat}"
    )
    print()
    print(
        "planned candidate semantic evaluations = "
        f"{run.candidate_run.planned_semantic_repeats}"
    )
    print(
        "maximum candidate physical Judge calls = "
        f"{run.candidate_run.max_possible_physical_attempts}"
    )
    print()
    print("No API call was made.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prompt v0.2-rc.1 paired development evaluation "
            "(Generator v0.1 baseline vs Prompt v0.2-rc.1)"
        ),
        usage=_USAGE,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="validate both populations and print the plan; never call the Judge",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="run the 90 rc.1 semantic evaluations and write artifacts",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    # ---- Offline pre-flight (no Judge, no API) ----
    try:
        run = prepare_development_evaluation()
    except DevelopmentEvaluationError as exc:
        print(f"ERROR: pre-flight failed: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        _print_dry_run(run)
        if args.output_dir is not None:
            write_development_artifacts(run, args.output_dir)
            print()
            print(f"Dry-run manifest written to: {args.output_dir}")
        return 0

    # ---- Formal mode ----
    # Fail fast BEFORE any Judge call and before the result directory exists,
    # so a missing credential can never degrade into rows of judge_api_error.
    # Only the key's PRESENCE is checked — never its value, never printed.
    judge = build_baseline_judge()
    if judge is None:
        print(
            "ERROR: OPENROUTER_API_KEY is not set (or is empty) in the "
            "environment.\n"
            "       The paired development evaluation requires the frozen Judge "
            "backend.\n"
            "       Aborting before any Judge call — no physical attempt was "
            "made and no\n"
            "       result run was created.\n"
            "       Use --dry-run for the offline pre-flight, which needs no key.",
            file=sys.stderr,
        )
        return 2

    out_dir = (
        Path(args.output_dir)
        if args.output_dir is not None
        else RESULTS_ROOT / run.run_id
    )

    execute_candidate_evaluation(run, judge)
    write_development_artifacts(run, out_dir)

    rows = case_pair_rows(run)
    pairs = [r for r in rows if r["pair_eligible"]]
    ops = run.candidate_run.repeat_results
    successful = sum(1 for r in ops if r.semantic_repeat_success)
    attempts = sum(r.attempt_count for r in ops)

    print(
        f"Completed: {successful} successful / "
        f"{len(ops) - successful} failed / "
        f"{PLANNED_SEMANTIC_REPEATS} planned rc.1 semantic repeats"
    )
    print(
        f"Physical attempts: {attempts} "
        f"(max possible {MAX_POSSIBLE_PHYSICAL_ATTEMPTS})"
    )
    print(
        f"Pair-eligible cases: {len(pairs)}/{CASE_COUNT} "
        f"(v0.1 eligible "
        f"{sum(1 for r in rows if r['v0_1_eligible'])}, "
        f"rc.1 eligible {sum(1 for r in rows if r['rc_1_eligible'])})"
    )
    print("Development evidence only — no PASS/FAIL threshold is computed.")
    print(f"Artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
