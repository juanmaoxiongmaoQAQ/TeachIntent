#!/usr/bin/env python3
"""Experiment driver for the formal Controlled Diagnostic Perturbation Validation.

Runs the frozen diagnostic dataset (24 pairs x 2 variants x 3 repeats = 144
evaluations) through the FROZEN Evaluator v0.1 with a real Judge, and saves
the FULL raw UniversalEvaluationArtifact / EvaluatorFailureArtifact per call.

This is experiment-side code only: it REUSES the frozen ``evaluate_speech_plan``
and the frozen ``evaluator_diagnostic.metrics`` functions, and does NOT modify
any frozen component (Evaluator, Generator, Prompt, Schemas, dataset, metrics).

Usage:
    set -a && source .env && set +a
    .venv/bin/python scripts/run_evaluator_diagnostic_experiment.py \
        --dataset cases/evaluator_diagnostic/diagnostic_pairs_v0.1.jsonl \
        --repeats 3 \
        --output-dir results/evaluator_diagnostic/<run_id>

Judge is built from JUDGE_API_KEY / JUDGE_PROVIDER / JUDGE_MODEL /
JUDGE_BASE_URL. The API key is NEVER printed, logged, or written to artifacts.

Frozen condition: evaluator v0.1, judge prompt v0.1, temperature 0, structured
output disabled, retry disabled, self-repair disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from teachintent.evaluator import (
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    EvaluationRunContext,
    JudgeClient,
    JudgeConfig,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
)
from teachintent.evaluator_diagnostic import (
    DIAGNOSTIC_DATASET_PATH,
    load_diagnostic_pairs,
    validate_diagnostic_dataset,
)
from teachintent.evaluator_diagnostic.metrics import (
    EvaluationRecord,
    critical_flag_diagnostics,
    directional_accuracy,
    mean_targeted_drop,
    off_target_mae,
    repeatability,
    _mean_scores,
    _union_flags,
)


def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dataset_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _build_judge() -> JudgeClient:
    api_key = os.environ.get("JUDGE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ERROR: JUDGE_API_KEY is not set; aborting (no dry-run).")
    return JudgeClient(
        api_key=api_key,
        base_url=os.environ.get("JUDGE_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.environ.get("JUDGE_MODEL", ""),
        provider=os.environ.get("JUDGE_PROVIDER", "openrouter"),
    )


def _reduce(record: dict, result) -> EvaluationRecord:
    """Reduce one full EvaluatorResult to an EvaluationRecord (mirrors frozen
    runner semantics exactly)."""
    artifact = result.artifact
    if artifact is not None and artifact.structural_valid:
        scores = {dim: artifact.scores[dim].score for dim in DIMENSION_IDS}
        flags = tuple(cf.flag for cf in artifact.critical_flags)
        return EvaluationRecord(
            pair_id=record["pair_id"], side=record["variant"],
            repeat_index=record["repeat_index"], scores=scores,
            critical_flags=flags, failure_type=None,
        )
    if artifact is not None and not artifact.structural_valid:
        return EvaluationRecord(
            pair_id=record["pair_id"], side=record["variant"],
            repeat_index=record["repeat_index"], scores=None,
            critical_flags=(), failure_type=f"gate_{artifact.gate_failure.stage}",
        )
    failure_type = result.failure.failure_type if result.failure is not None else "unknown"
    return EvaluationRecord(
        pair_id=record["pair_id"], side=record["variant"],
        repeat_index=record["repeat_index"], scores=None,
        critical_flags=(), failure_type=failure_type,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DIAGNOSTIC_DATASET_PATH)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(f"ERROR: dataset file not found: {args.dataset}")
        return 2
    if args.repeats < 1:
        print(f"ERROR: --repeats must be >= 1")
        return 2

    # Preflight: validate dataset.
    validation = validate_diagnostic_dataset(args.dataset)
    if not validation.all_passed:
        print("ERROR: dataset failed structural validation; aborting.")
        return 2

    pairs = load_diagnostic_pairs(args.dataset)
    dataset_sha = _dataset_sha256(args.dataset)

    judge = _build_judge()
    judge_config = JudgeConfig(
        judge_provider=judge.provider,
        judge_model_requested=judge.model,
        temperature=0,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        judge_prompt_sha256=compute_judge_prompt_sha256(),
        structured_output_enabled=judge.structured_output_enabled,
        retry_enabled=False,
        self_repair_enabled=False,
    )

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = _canonical_utc_now()

    print(f"Judge provider: {judge.provider}")
    print(f"Judge model (requested): {judge.model}")
    print(f"Judge prompt: {JUDGE_PROMPT_VERSION}")
    print(f"Evaluator: {EVALUATOR_VERSION}")
    print(f"Dataset: {args.dataset}")
    print(f"Dataset SHA-256: {dataset_sha}")
    print(f"Condition: temperature=0, structured_output=False, retry=False, self_repair=False")
    print(f"Expected calls: {len(pairs) * 2 * args.repeats}")
    print()

    records: list[EvaluationRecord] = []
    evals_path = out_dir / "evaluations.jsonl"
    successful = 0
    failed = 0
    failure_counts: dict[str, int] = {}
    reported_models: set[str] = set()

    # Run all evaluations; write each raw artifact immediately (append).
    with evals_path.open("w", encoding="utf-8") as handle:
        for pair in pairs:
            for variant, plan in (("reference", pair["reference_plan"]),
                                  ("degraded", pair["degraded_plan"])):
                for repeat_index in range(args.repeats):
                    eval_id = f"{pair['pair_id']}__{variant}__r{repeat_index + 1}"
                    ctx = EvaluationRunContext(
                        input_case_id=eval_id,
                        generator_version="v0.1",
                        prompt_version="v0.1",
                    )
                    raw = json.dumps(plan, ensure_ascii=False)
                    result = evaluate_speech_plan(
                        pair["input"], raw, ctx, judge_config, judge
                    )

                    # Capture full raw artifact / failure.
                    artifact_dump = None
                    failure_dump = None
                    outcome = None
                    if result.artifact is not None:
                        outcome = "artifact"
                        artifact_dump = result.artifact.model_dump(mode="json")
                        if result.artifact.structural_valid:
                            successful += 1
                        else:
                            failed += 1
                            failure_counts["gate_" + result.artifact.gate_failure.stage] = (
                                failure_counts.get("gate_" + result.artifact.gate_failure.stage, 0) + 1
                            )
                        rm = result.artifact.run_metadata.judge_model_reported
                        if rm:
                            reported_models.add(rm)
                    elif result.failure is not None:
                        outcome = "failure"
                        failure_dump = result.failure.model_dump(mode="json")
                        failed += 1
                        ft = result.failure.failure_type
                        failure_counts[ft] = failure_counts.get(ft, 0) + 1
                    else:  # pragma: no cover — defensive
                        outcome = "unknown"
                        failed += 1
                        failure_counts["unknown"] = failure_counts.get("unknown", 0) + 1

                    record = {
                        "evaluation_id": eval_id,
                        "pair_id": pair["pair_id"],
                        "family": pair["family"],
                        "variant": variant,
                        "repeat_index": repeat_index,
                        "outcome": outcome,
                        "artifact": artifact_dump,
                        "failure": failure_dump,
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                    records.append(_reduce(record, result))

    completed_at = _canonical_utc_now()

    # ---- Frozen metrics ----
    da = directional_accuracy(records, pairs)
    mtd = mean_targeted_drop(records, pairs)
    omae = off_target_mae(records, pairs)
    rep = repeatability(records, pairs)
    flags = critical_flag_diagnostics(records, pairs)

    # ---- Family breakdown ----
    family_breakdown = {}
    for fam in sorted({p["family"] for p in pairs}):
        fam_pairs = [p for p in pairs if p["family"] == fam]
        fda = directional_accuracy(records, fam_pairs)
        fmtd = mean_targeted_drop(records, fam_pairs)
        fomae = off_target_mae(records, fam_pairs)
        fflags = critical_flag_diagnostics(records, fam_pairs)
        family_breakdown[fam] = {
            "pairs": len(fam_pairs),
            "target_dimensions": sorted({d for p in fam_pairs for d in p["target_dimensions"]}),
            "directional_accuracy": {
                "numerator": fda.numerator, "denominator": fda.denominator,
                "accuracy": fda.accuracy,
            },
            "mean_targeted_drop": fmtd.mean_drop,
            "off_target_mae": fomae.mae,
            "critical_flags": {"tp": fflags.tp, "fn": fflags.fn, "fp": fflags.fp},
        }

    # ---- Run manifest (experiment-side, includes dataset_sha256) ----
    manifest = {
        "run_id": out_dir.name,
        "started_at": started_at,
        "completed_at": completed_at,
        "dataset_path": str(args.dataset),
        "dataset_sha256": dataset_sha,
        "pair_count": len(pairs),
        "plan_count": len(pairs) * 2,
        "repeats": args.repeats,
        "expected_evaluator_calls": len(pairs) * 2 * args.repeats,
        "successful_evaluations": successful,
        "failed_evaluations": failed,
        "failure_taxonomy": failure_counts,
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": judge.provider,
        "judge_model_requested": judge.model,
        "judge_model_reported": sorted(reported_models),
        "temperature": 0,
        "structured_output_enabled": judge.structured_output_enabled,
        "retry_enabled": False,
        "self_repair_enabled": False,
    }
    _write_json(out_dir / "run_manifest.json", manifest)

    # ---- Summary ----
    summary = {
        "run_id": out_dir.name,
        "started_at": started_at,
        "completed_at": completed_at,
        "dataset_sha256": dataset_sha,
        "pair_count": len(pairs),
        "plan_count": len(pairs) * 2,
        "repeats": args.repeats,
        "expected_evaluator_calls": len(pairs) * 2 * args.repeats,
        "successful_evaluations": successful,
        "failed_evaluations": failed,
        "failure_taxonomy": failure_counts,
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": judge.provider,
        "judge_model_requested": judge.model,
        "judge_model_reported": sorted(reported_models),
        "temperature": 0,
        "structured_output_enabled": judge.structured_output_enabled,
        "retry_enabled": False,
        "self_repair_enabled": False,
        "metrics": {
            "directional_accuracy": {
                "numerator": da.numerator,
                "denominator": da.denominator,
                "accuracy": da.accuracy,
                "skipped": da.skipped,
                "passed": da.passed,
                "threshold": 0.85,
            },
            "mean_targeted_drop": {
                "n": mtd.n, "mean_drop": mtd.mean_drop, "skipped": mtd.skipped,
                "passed": mtd.passed, "threshold": 1.0,
            },
            "off_target_mae": {
                "n": omae.n, "mae": omae.mae, "skipped": omae.skipped,
                "passed": omae.passed, "threshold": 0.5,
            },
            "repeatability": {
                "n_pairs": rep.n_pairs,
                "exact_agreement": rep.exact_agreement,
                "within_one_agreement": rep.within_one_agreement,
                "passed": rep.passed,
                "threshold": 0.95,
            },
            "critical_flags": {
                "tp": flags.tp, "fn": flags.fn, "fp": flags.fp,
                "expected_flags": flags.expected_flags,
                "non_expected_cases": flags.non_expected_cases,
                "per_pair": flags.per_pair,
            },
        },
        "family_breakdown": family_breakdown,
        "pass_fail": {
            "directional_accuracy": da.passed,
            "mean_targeted_drop": mtd.passed,
            "off_target_mae": omae.passed,
            "repeatability": rep.passed,
            "overall": "PASS" if (da.passed and mtd.passed and omae.passed and rep.passed) else "FAIL",
        },
    }
    _write_json(out_dir / "summary.json", summary)

    # ---- Pair metrics CSV ----
    _write_pair_metrics_csv(out_dir / "pair_metrics.csv", pairs, records)

    # ---- README ----
    (out_dir / "README.md").write_text(
        f"""# Evaluator Diagnostic Validation — run {out_dir.name}

- started_at: {started_at}
- completed_at: {completed_at}
- dataset: {args.dataset}
- dataset_sha256: {dataset_sha}
- pairs: {len(pairs)} / plans: {len(pairs) * 2} / repeats: {args.repeats}
- expected calls: {len(pairs) * 2 * args.repeats}
- successful: {successful} / failed: {failed}
- evaluator_version: {EVALUATOR_VERSION}
- judge_prompt_version: {JUDGE_PROMPT_VERSION}
- judge_provider: {judge.provider}
- judge_model_requested: {judge.model}
- judge_model_reported: {sorted(reported_models)}

Artifacts: run_manifest.json / summary.json / evaluations.jsonl /
pair_metrics.csv. This directory is git-ignored (results/). Do not commit.
""", encoding="utf-8")

    print()
    print(f"Completed: {successful} successful / {failed} failed / {len(records)} total")
    print(f"Artifacts: {out_dir}")
    print(f"Directional accuracy: {da.numerator}/{da.denominator} = {da.accuracy} (passed={da.passed})")
    print(f"Mean targeted drop: {mtd.mean_drop} (passed={mtd.passed})")
    print(f"Off-target MAE: {omae.mae} (passed={omae.passed})")
    print(f"Within-one repeat: {rep.within_one_agreement} (passed={rep.passed})")
    print(f"Flags: TP={flags.tp} FN={flags.fn} FP={flags.fp}")
    overall = "PASS" if (da.passed and mtd.passed and omae.passed and rep.passed) else "FAIL"
    print(f"Overall: {overall}")
    return 0


def _write_pair_metrics_csv(path: Path, pairs, records) -> None:
    import csv
    header = [
        "pair_id", "family", "target_dimensions", "expected_flags",
        "ref_mean_target", "deg_mean_target", "targeted_drop", "off_target_mae",
        "reference_critical_flags", "degraded_critical_flags",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for pair in pairs:
            pid = pair["pair_id"]
            target = pair["target_dimensions"]
            ref = _mean_scores(records, pid, "reference")
            deg = _mean_scores(records, pid, "degraded")
            ref_flags = sorted(_union_flags(records, pid, "reference"))
            deg_flags = sorted(_union_flags(records, pid, "degraded"))
            if ref is None or deg is None:
                writer.writerow([pid, pair["family"], "|".join(target),
                                 "|".join(pair["expected_flags"]),
                                 "", "", "", "", "|".join(ref_flags), "|".join(deg_flags)])
                continue
            ref_target = sum(ref[d] for d in target) / len(target)
            deg_target = sum(deg[d] for d in target) / len(target)
            drop = round(ref_target - deg_target, 4)
            off = [abs(ref[d] - deg[d]) for d in DIMENSION_IDS if d not in target]
            mae = round(sum(off) / len(off), 4) if off else 0.0
            writer.writerow([
                pid, pair["family"], "|".join(target), "|".join(pair["expected_flags"]),
                round(ref_target, 4), round(deg_target, 4), drop, mae,
                "|".join(ref_flags), "|".join(deg_flags),
            ])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
