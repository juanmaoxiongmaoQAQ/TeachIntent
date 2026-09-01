#!/usr/bin/env python3
"""Prompt v0.2 candidate paired development evaluation — runner CLI.

Compares the FINISHED Generator v0.1 baseline (Prompt v0.1) against a FINISHED
candidate generation run, using the SAME frozen Evaluator v0.1 acquisition
policy as Protocol v0.2
(``docs/generator_v0.1_evaluation_protocol_v0.2.md``, Status: **Frozen**).

The candidate side is selected with ``--prompt-version``; rc.1 stays the
DEFAULT so the existing rc.1 evaluation remains reproducible with no arguments.
Selecting rc.2 changes only which finished generation run is loaded — never
the protocol, the retry taxonomy, the reducer, or any aggregation formula.

    --prompt-version v0.2-rc.1   (default)  generation run 20260831-052126
    --prompt-version v0.2-rc.2   (explicit) generation run 20260831-153546

Neither side is regenerated:

    v0.1 generation   three canonical Pilot runs (A/B/C = 12/12/6), reused
    v0.1 evaluation   baseline run 20260830T095934Z, reused READ-ONLY
    candidate gen.    development run (per version above), reused READ-ONLY
    candidate eval.   NEW — the only Judge calls in this experiment

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

    # rc.2 offline pre-flight (explicitly requested — rc.2 is never a default).
    .venv/bin/python scripts/run_prompt_v0_2_rc1_development_evaluation.py \
        --dry-run --prompt-version v0.2-rc.2

    # Formal run (requires OPENROUTER_API_KEY). Without the key the run aborts
    # with exit code 2 BEFORE the first attempt and before any result directory
    # is created.
    .venv/bin/python scripts/run_prompt_v0_2_rc1_development_evaluation.py \
        --execute --prompt-version v0.2-rc.2

Artifacts go to ``results/prompt_v0_2_rc{1,2}_development_evaluation/<run_id>/``
according to the selected candidate.

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
    CANDIDATE_PROMPT_VERSION,
    CASE_COUNT,
    MAX_POSSIBLE_PHYSICAL_ATTEMPTS,
    PLANNED_SEMANTIC_REPEATS,
    PROMPT_VERSION_RC2,
    SUPPORTED_PROMPT_VERSIONS,
    DevelopmentEvaluationError,
    case_pair_rows,
    evaluation_results_root_for_prompt_version,
    execute_candidate_evaluation,
    prepare_development_evaluation,
    summarize_candidate_delivery_behavior,
    write_development_artifacts,
)

_USAGE = (
    "usage: run_prompt_v0_2_rc1_development_evaluation.py "
    "{--dry-run | --execute} [--prompt-version VERSION]\n"
    "  --dry-run   validate both populations, assert cross-side identity and\n"
    "              print the plan; never constructs a Judge, never calls the\n"
    "              API, never creates a result run.\n"
    "  --execute   run the 90 candidate semantic evaluations with the frozen\n"
    "              Judge and write the paired comparison artifacts.\n"
    "\n"
    "  --prompt-version {v0.2-rc.1,v0.2-rc.2}\n"
    "              candidate prompt under evaluation. rc.1 is the DEFAULT, so\n"
    "              the existing rc.1 evaluation stays reproducible; rc.2 must\n"
    "              be requested explicitly.\n"
    "\n"
    "  Exactly one of --dry-run / --execute is required; neither or both is an\n"
    "  error. The v0.1 side is never regenerated and never re-evaluated."
)


def _print_dry_run(run) -> None:
    integrity = run.integrity
    prompt_version = run.candidate_prompt_version
    title = f"Prompt {prompt_version} Paired Development Evaluation — Dry-Run"
    print(f"=== {title} ===")
    print()
    print(f"baseline population = {len(run.baseline.case_rows)}")
    print(f"candidate population = {integrity.total_cases}")
    print(f"case IDs exact match = {integrity.case_ids_exact_match}")
    print(f"input fingerprints match = {integrity.input_fingerprints_match}")
    print()
    print(f"baseline evaluation run = {run.baseline.run_id}")
    print(f"candidate generation run = {run.candidate_generation_run_id}")
    print()
    print(f"candidate prompt = {prompt_version}")
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
    # The measured delivery_plan distribution is reported next to the plan
    # because the D5 result must never be read without it (mode-collapse risk).
    delivery = summarize_candidate_delivery_behavior(run)
    print(
        f"candidate delivery_plan (measured) = "
        f"empty {delivery['empty_count']} / non-empty "
        f"{delivery['non_empty_count']}"
    )
    if delivery["non_empty_case_ids"]:
        print(
            "non-empty case IDs = "
            + ", ".join(delivery["non_empty_case_ids"])
        )
    print(
        "  (D5 and this distribution must be read together — a high D5 alone "
        "does not rule out mode collapse.)"
    )
    print()
    print("No API call was made.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prompt v0.2 candidate paired development evaluation "
            "(Generator v0.1 baseline vs Prompt v0.2-rc.1 / v0.2-rc.2)"
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
        help=(
            "run the 90 candidate semantic evaluations and write artifacts "
            "(requires OPENROUTER_API_KEY)"
        ),
    )
    parser.add_argument(
        "--prompt-version",
        choices=sorted(SUPPORTED_PROMPT_VERSIONS),
        default=CANDIDATE_PROMPT_VERSION,
        help=(
            "candidate prompt under evaluation (default: %(default)s; "
            f"{PROMPT_VERSION_RC2} must be requested explicitly)"
        ),
    )
    parser.add_argument(
        "--candidate-run",
        default=None,
        help=(
            "override the candidate generation run directory (still asserted "
            "to be the finished run recorded for the selected prompt version)"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    # ---- Offline pre-flight (no Judge, no API) ----
    try:
        run = prepare_development_evaluation(
            candidate_root=args.candidate_run,
            prompt_version=args.prompt_version,
        )
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
        else evaluation_results_root_for_prompt_version(args.prompt_version)
        / run.run_id
    )

    execute_candidate_evaluation(run, judge)
    write_development_artifacts(run, out_dir)

    rows = case_pair_rows(run)
    pairs = [r for r in rows if r["pair_eligible"]]
    ops = run.candidate_run.repeat_results
    successful = sum(1 for r in ops if r.semantic_repeat_success)
    attempts = sum(r.attempt_count for r in ops)
    label = run.candidate_label

    print(
        f"Completed: {successful} successful / "
        f"{len(ops) - successful} failed / "
        f"{PLANNED_SEMANTIC_REPEATS} planned {label} semantic repeats"
    )
    print(
        f"Physical attempts: {attempts} "
        f"(max possible {MAX_POSSIBLE_PHYSICAL_ATTEMPTS})"
    )
    print(
        f"Pair-eligible cases: {len(pairs)}/{CASE_COUNT} "
        f"(v0.1 eligible "
        f"{sum(1 for r in rows if r['v0_1_eligible'])}, "
        f"{label} eligible {sum(1 for r in rows if r[f'{label}_eligible'])})"
    )
    delivery = summarize_candidate_delivery_behavior(run)
    print(
        f"Delivery behaviour: empty {delivery['empty_count']} / "
        f"non-empty {delivery['non_empty_count']} — must be read together "
        "with D5."
    )
    print("Development evidence only — no PASS/FAIL threshold is computed.")
    print(f"Artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
