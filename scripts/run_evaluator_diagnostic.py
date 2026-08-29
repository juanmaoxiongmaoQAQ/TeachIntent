#!/usr/bin/env python3
"""Run the TeachIntent Evaluator diagnostic perturbation validation.

Evaluates each diagnostic pair's reference and degraded plan through the
frozen Evaluator v0.1, independently, for a configurable number of repeats.

Usage:
    .venv/bin/python scripts/run_evaluator_diagnostic.py --dry-run            # validate only
    .venv/bin/python scripts/run_evaluator_diagnostic.py \
        --dataset cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl \
        --repeats 3 --output-dir results/evaluator_diagnostic/<run_id>

Options:
    --dataset PATH      diagnostic pairs JSONL (default: frozen dataset)
    --repeats N         number of repeated evaluations per plan (default 3)
    --output-dir DIR    directory to write artifacts under (default:
                        results/evaluator_diagnostic/<run_id>)
    --dry-run           validate the dataset and write a manifest WITHOUT any
                        judge call (default when no judge is configured)

The judge backend is built from the environment (JUDGE_API_KEY /
JUDGE_BASE_URL / JUDGE_MODEL / JUDGE_PROVIDER), defaulting to the OpenRouter
``tencent/hy3`` baseline. If JUDGE_API_KEY is not set, this script runs in
dry-run mode and never calls the API.

The API key is NEVER written to any artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from teachintent.evaluator import JudgeClient
from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_DATASET_PATH,
    build_judge_config,
    run_diagnostic,
    run_diagnostic_dry,
)
from teachintent.evaluator_diagnostic.metrics import (
    critical_flag_diagnostics,
    directional_accuracy,
    mean_targeted_drop,
    off_target_mae,
    repeatability,
)
from teachintent.evaluator_diagnostic.dataset import load_diagnostic_pairs

RESULTS_ROOT = Path(__file__).resolve().parents[1] / "results" / "evaluator_diagnostic"


def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_judge() -> JudgeClient | None:
    """Build a JudgeClient from env, or None if JUDGE_API_KEY is absent."""
    api_key = os.environ.get("JUDGE_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get("JUDGE_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("JUDGE_MODEL", "tencent/hy3")
    provider = os.environ.get("JUDGE_PROVIDER", "openrouter")
    return JudgeClient(
        api_key=api_key, base_url=base_url, model=model, provider=provider,
    )


def _write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DIAGNOSTIC_DATASET_PATH)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(f"ERROR: dataset file not found: {args.dataset}")
        return 2

    if args.repeats < 1:
        print(f"ERROR: --repeats must be >= 1, got {args.repeats}")
        return 2

    judge = _build_judge()
    dry_run = args.dry_run or judge is None

    if dry_run:
        if judge is None and not args.dry_run:
            print("NOTE: JUDGE_API_KEY not set; running in dry-run mode (no API call).")
        result = run_diagnostic_dry(args.dataset, repeats=args.repeats)
    else:
        result = run_diagnostic(args.dataset, judge, repeats=args.repeats)

    # ---- Determine output directory ----
    if args.output_dir is not None:
        out_dir = args.output_dir
    else:
        out_dir = RESULTS_ROOT / result.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = load_diagnostic_pairs(args.dataset)

    # ---- Build summary + metrics ----
    summary: dict = {
        "run_id": result.run_id,
        "started_at": result.started_at,
        "dataset_path": result.dataset_path,
        "repeats": result.repeats,
        "dry_run": result.dry_run,
        "evaluator_version": result.evaluator_version,
        "judge_provider": result.judge_provider or None,
        "judge_model_requested": result.judge_model_requested or None,
        "judge_prompt_version": result.judge_prompt_version,
        "pair_count": len(pairs),
        "validator": result.validator,
        "metrics": None,
    }

    if not dry_run:
        da = directional_accuracy(result.records, pairs)
        mtd = mean_targeted_drop(result.records, pairs)
        omae = off_target_mae(result.records, pairs)
        rep = repeatability(result.records, pairs)
        flags = critical_flag_diagnostics(result.records, pairs)
        summary["metrics"] = {
            "directional_accuracy": {
                "numerator": da.numerator,
                "denominator": da.denominator,
                "accuracy": da.accuracy,
                "skipped": da.skipped,
                "passed": da.passed,
            },
            "mean_targeted_drop": {
                "n": mtd.n,
                "mean_drop": mtd.mean_drop,
                "skipped": mtd.skipped,
                "passed": mtd.passed,
            },
            "off_target_mae": {
                "n": omae.n,
                "mae": omae.mae,
                "skipped": omae.skipped,
                "passed": omae.passed,
            },
            "repeatability": {
                "n_pairs": rep.n_pairs,
                "exact_agreement": rep.exact_agreement,
                "within_one_agreement": rep.within_one_agreement,
                "passed": rep.passed,
            },
            "critical_flags": {
                "tp": flags.tp,
                "fn": flags.fn,
                "fp": flags.fp,
                "expected_flags": flags.expected_flags,
                "non_expected_cases": flags.non_expected_cases,
            },
        }

    # ---- Write artifacts ----
    _write_json(out_dir / "run_manifest.json", {
        "run_id": result.run_id,
        "started_at": result.started_at,
        "dataset_path": result.dataset_path,
        "repeats": result.repeats,
        "dry_run": result.dry_run,
        "evaluator_version": result.evaluator_version,
        "judge_provider": result.judge_provider or None,
        "judge_model_requested": result.judge_model_requested or None,
        "judge_prompt_version": result.judge_prompt_version,
    })
    _write_json(out_dir / "summary.json", summary)

    if not dry_run:
        with (out_dir / "evaluations.jsonl").open("w", encoding="utf-8") as handle:
            for rec in result.records:
                handle.write(json.dumps({
                    "pair_id": rec.pair_id,
                    "side": rec.side,
                    "repeat_index": rec.repeat_index,
                    "scores": rec.scores,
                    "critical_flags": list(rec.critical_flags),
                    "failure_type": rec.failure_type,
                }, ensure_ascii=False) + "\n")

        _write_pair_metrics_csv(out_dir / "pair_metrics.csv", pairs, result.records)

    (out_dir / "README.md").write_text(
        _readme_text(result, dry_run), encoding="utf-8"
    )

    print(f"Run ID:   {result.run_id}")
    print(f"Dry run:  {dry_run}")
    print(f"Artifacts: {out_dir}")
    if not dry_run:
        m = summary["metrics"]
        print(
            f"Directional accuracy: {m['directional_accuracy']['numerator']}/"
            f"{m['directional_accuracy']['denominator']}"
            f" = {m['directional_accuracy']['accuracy']}"
        )
        print(
            f"Mean targeted drop:   {m['mean_targeted_drop']['mean_drop']}"
            f" (n={m['mean_targeted_drop']['n']})"
        )
        print(f"Off-target MAE:       {m['off_target_mae']['mae']}")
        print(
            f"Within-one repeat:    {m['repeatability']['within_one_agreement']}"
        )
        print(
            f"Flags: TP={m['critical_flags']['tp']} "
            f"FN={m['critical_flags']['fn']} FP={m['critical_flags']['fp']}"
        )
    return 0


def _write_pair_metrics_csv(path: Path, pairs, records) -> None:
    """Write one row per pair: mean target-dim drop + off-target MAE."""
    import csv
    from teachintent.evaluator_diagnostic.metrics import _mean_scores
    from teachintent.evaluator.rubric import DIMENSION_IDS

    header = [
        "pair_id", "family", "target_dimensions",
        "ref_mean_target", "deg_mean_target", "targeted_drop",
        "off_target_mae",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for pair in pairs:
            pid = pair["pair_id"]
            target = pair["target_dimensions"]
            ref = _mean_scores(records, pid, "reference")
            deg = _mean_scores(records, pid, "degraded")
            if ref is None or deg is None:
                writer.writerow([pid, pair["family"], "|".join(target), "", "", "", ""])
                continue
            ref_target = sum(ref[d] for d in target) / len(target)
            deg_target = sum(deg[d] for d in target) / len(target)
            drop = round(ref_target - deg_target, 4)
            off = [abs(ref[d] - deg[d]) for d in DIMENSION_IDS if d not in target]
            mae = round(sum(off) / len(off), 4) if off else 0.0
            writer.writerow([
                pid, pair["family"], "|".join(target),
                round(ref_target, 4), round(deg_target, 4), drop, mae,
            ])


def _readme_text(result, dry_run: bool) -> str:
    lines = [
        "# Evaluator Diagnostic Run",
        "",
        f"- run_id: {result.run_id}",
        f"- started_at: {result.started_at}",
        f"- dataset: {result.dataset_path}",
        f"- repeats: {result.repeats}",
        f"- dry_run: {dry_run}",
        f"- evaluator_version: {result.evaluator_version}",
        f"- judge_prompt_version: {result.judge_prompt_version}",
    ]
    if not dry_run:
        lines += [
            f"- judge_provider: {result.judge_provider}",
            f"- judge_model_requested: {result.judge_model_requested}",
        ]
    lines += [
        "",
        "Artifacts:",
        "- run_manifest.json — run-level manifest",
        "- summary.json — metrics summary",
        "- evaluations.jsonl — one line per (pair, side, repeat) evaluation",
        "- pair_metrics.csv — per-pair target drop / off-target MAE",
        "",
        "NOTE: this directory is git-ignored (results/). Do not commit.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
