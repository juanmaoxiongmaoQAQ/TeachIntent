#!/usr/bin/env python3
"""Run the lightweight Prompt v0.1 vs v0.2 release sanity comparison."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from teachintent.generator.client import Hy3Client
from teachintent.generator_evaluation.baseline_v0_1 import build_baseline_judge
from teachintent.release_sanity import (
    GENERATOR_BASE_URL,
    GENERATOR_MODEL,
    GENERATOR_TIMEOUT_SECONDS,
    MAX_ATTEMPTS_PER_SEMANTIC_REPEAT,
    PLANNED_GENERATIONS,
    PLANNED_SEMANTIC_EVALUATIONS,
    ReleaseSanityError,
    generation_schedule,
    load_jsonl,
    run_release_sanity,
    validate_release_sanity_dataset,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TeachIntent Prompt v0.1 vs frozen v0.2 release sanity"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    report = validate_release_sanity_dataset()
    if not report["valid"]:
        print("ERROR: dataset validation failed", file=sys.stderr)
        for error in report["errors"]:
            print(f"  - {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        records = load_jsonl(report["dataset_path"])
        schedule = generation_schedule(records)
        print("=== TeachIntent Release Sanity — Offline Preflight ===")
        print(f"dataset valid = true")
        print(f"dataset SHA-256 = {report['dataset_sha256']}")
        print(f"cases = {report['case_count']}")
        print(f"planned generations = {len(schedule)} / expected {PLANNED_GENERATIONS}")
        print(f"planned semantic evaluations = {PLANNED_SEMANTIC_EVALUATIONS}")
        print(f"semantic repeats per plan = 1")
        print(f"max physical attempts = {MAX_ATTEMPTS_PER_SEMANTIC_REPEAT}")
        print("No API call was made.")
        return 0

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print(
            "ERROR: OPENROUTER_API_KEY is missing/empty; aborting before any API call",
            file=sys.stderr,
        )
        return 2

    generator_client = Hy3Client(
        api_key=key,
        base_url=GENERATOR_BASE_URL,
        model=GENERATOR_MODEL,
        timeout=GENERATOR_TIMEOUT_SECONDS,
    )
    judge = build_baseline_judge()
    if judge is None:
        print("ERROR: unable to construct frozen Judge", file=sys.stderr)
        return 2

    try:
        run_dir, summary = run_release_sanity(
            generator_client, judge, output_dir=args.output_dir
        )
    except ReleaseSanityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Artifacts: {run_dir}")
    print(
        "Generation valid plans: "
        f"v0.1 {summary['generation']['v0.1']['valid_plan_count']}/12, "
        f"v0.2 {summary['generation']['v0.2']['valid_plan_count']}/12"
    )
    print(
        "Evaluation artifacts: "
        f"v0.1 {summary['evaluation']['v0.1']['successful_artifacts']}/12, "
        f"v0.2 {summary['evaluation']['v0.2']['successful_artifacts']}/12"
    )
    print("RELEASE SANITY EVIDENCE — NOT FORMAL CONFIRMATORY EVIDENCE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
