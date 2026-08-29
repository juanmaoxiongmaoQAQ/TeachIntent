"""Protocol v0.2 confirmatory runner — orchestration, execution, aggregation, artifacts.

Decouples orchestration from metric aggregation: all frozen metric math lives in
:mod:`teachintent.evaluator_diagnostic.protocol_v0_2`; this module only:

* verifies dataset/protocol integrity (fail-fast) and plans the 144 calls;
* builds the frozen judge config (binding the actual backend against the frozen
  provider/model/condition);
* executes each plan once through the frozen ``evaluate_speech_plan`` (real mode
  only — never called in this implementation phase);
* reduces results to :class:`ConfirmatoryRecord` (never converting a failure to
  a semantic zero);
* aggregates via the frozen v0.2 metrics;
* writes the confirmatory artifact set.

Only ``case["input"]`` and one plan reach the Evaluator; experiment metadata
(``pair_id``, ``family``, ``expected_flags``, dimension partition, notes) is
never passed to the Judge (the Evaluator's sanitizer already excludes it).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ..evaluator import (
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    EvaluationRunContext,
    JudgeCompleter,
    JudgeClient,
    JudgeConfig,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
)
from .dataset import load_diagnostic_pairs
from .holdout import validate_protocol_metadata
from .protocol_v0_2 import (
    CONFIRMATORY_DATASET_PATH,
    EXPECTED_CALLS,
    ConfirmatoryRecord,
    IntegrityReport,
    verify_dataset_integrity,
)
from . import protocol_v0_2 as P

__all__ = [
    "ConfirmatoryRun",
    "DatasetIntegrityError",
    "build_frozen_judge_config",
    "build_confirmatory_judge",
    "plan_confirmatory_calls",
    "prepare_confirmatory_run",
    "evaluate_one",
    "reduce_result",
    "execute_confirmatory_run",
    "aggregate",
    "build_manifest",
    "build_summary",
    "write_artifacts",
]

GENERATOR_VERSION = "v0.1"
PROMPT_VERSION = "v0.1"


class DatasetIntegrityError(RuntimeError):
    """Raised when the frozen holdout dataset fails the pre-flight integrity check."""


def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Frozen judge config.
# ---------------------------------------------------------------------------
def build_frozen_judge_config(judge: JudgeCompleter) -> JudgeConfig:
    """Build the frozen JudgeConfig, binding the actual judge backend against the
    frozen provider/model/condition. Raises ``ValueError`` on any mismatch so an
    artifact can never claim model/provider A while actually calling B."""
    if judge.provider != P.FROZEN_JUDGE_PROVIDER:
        raise ValueError(
            f"judge provider mismatch: backend={judge.provider!r}, "
            f"frozen={P.FROZEN_JUDGE_PROVIDER!r}"
        )
    if judge.model != P.FROZEN_JUDGE_MODEL_REQUESTED:
        raise ValueError(
            f"judge model mismatch: backend={judge.model!r}, "
            f"frozen={P.FROZEN_JUDGE_MODEL_REQUESTED!r}"
        )
    if judge.structured_output_enabled:
        raise ValueError(
            "structured_output_enabled must be False for the frozen confirmatory condition"
        )
    return JudgeConfig(
        judge_provider=judge.provider,
        judge_model_requested=judge.model,
        temperature=P.FROZEN_TEMPERATURE,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        judge_prompt_sha256=compute_judge_prompt_sha256(),
        structured_output_enabled=P.FROZEN_STRUCTURED_OUTPUT_ENABLED,
        retry_enabled=P.FROZEN_RETRY_ENABLED,
        self_repair_enabled=P.FROZEN_SELF_REPAIR_ENABLED,
    )


def build_confirmatory_judge(env: dict[str, str] | None = None) -> JudgeClient | None:
    """Build a JudgeClient from the frozen condition + ``OPENROUTER_API_KEY``.

    The provider/model/base-url are FROZEN (never read from env); only the API
    key comes from the environment. Returns ``None`` when no key is present
    (caller should treat this as dry-run). The key is never printed or stored.
    """
    env = env if env is not None else os.environ
    api_key = (env.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None
    return JudgeClient(
        api_key=api_key,
        base_url=P.FROZEN_JUDGE_BASE_URL,
        model=P.FROZEN_JUDGE_MODEL_REQUESTED,
        provider=P.FROZEN_JUDGE_PROVIDER,
    )


# ---------------------------------------------------------------------------
# Call planning.
# ---------------------------------------------------------------------------
def plan_confirmatory_calls(
    pairs: Sequence[dict], repeats: int = P.REPEATS
) -> list[dict]:
    """Return the full confirmatory call plan (24 x 2 x repeats = 144)."""
    calls: list[dict] = []
    for pair in pairs:
        for variant in ("reference", "degraded"):
            for repeat_index in range(1, repeats + 1):
                calls.append(
                    {
                        "pair_id": pair["pair_id"],
                        "family": pair["family"],
                        "variant": variant,
                        "repeat_index": repeat_index,
                    }
                )
    return calls


# ---------------------------------------------------------------------------
# Result dataclass.
# ---------------------------------------------------------------------------
@dataclass
class ConfirmatoryRun:
    run_id: str
    started_at: str
    completed_at: str | None = None
    dry_run: bool = True
    dataset_path: str = ""
    dataset_sha256: str = ""
    protocol_metadata_sha256: str = ""
    protocol_document_sha256: str = ""
    freeze_record: dict = field(default_factory=dict)
    integrity: IntegrityReport | None = None
    metadata: dict = field(default_factory=dict)
    pairs: list[dict] = field(default_factory=list)
    repeats: int = P.REPEATS
    planned_calls: int = 0
    judge_provider: str | None = None
    judge_model_requested: str | None = None
    judge_model_reported: tuple[str, ...] = ()
    records: tuple[ConfirmatoryRecord, ...] = ()
    raw_evaluations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prepare (integrity + metadata + plan; no API).
# ---------------------------------------------------------------------------
def prepare_confirmatory_run(
    dataset_path: Path | str = CONFIRMATORY_DATASET_PATH,
    *,
    repeats: int = P.REPEATS,
) -> ConfirmatoryRun:
    """Verify integrity + metadata and plan the run. Never calls the Judge."""
    if repeats < 1:
        raise ValueError(f"repeats must be >= 1, got {repeats}")
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    dataset_sha = _sha256_file(dataset_path)
    integrity = verify_dataset_integrity(dataset_path)
    if not integrity.ok:
        raise DatasetIntegrityError("; ".join(integrity.messages))

    metadata = P.load_protocol_metadata()
    meta_report = validate_protocol_metadata()
    if not meta_report.all_passed:
        raise ValueError(
            "protocol metadata failed validation: " + "; ".join(meta_report.case_errors)
        )

    pairs = load_diagnostic_pairs(dataset_path)
    calls = plan_confirmatory_calls(pairs, repeats)

    return ConfirmatoryRun(
        run_id=_utc_run_id(),
        started_at=_canonical_utc_now(),
        dry_run=True,
        dataset_path=str(dataset_path),
        dataset_sha256=dataset_sha,
        protocol_metadata_sha256=_sha256_file(P.PROTOCOL_METADATA_PATH),
        protocol_document_sha256=_sha256_file(P.PROTOCOL_DOC_PATH),
        freeze_record=P.load_freeze_record(),
        integrity=integrity,
        metadata=metadata,
        pairs=pairs,
        repeats=repeats,
        planned_calls=len(calls),
    )


# ---------------------------------------------------------------------------
# Execution (real mode only; not called in this phase).
# ---------------------------------------------------------------------------
def evaluate_one(
    pair: dict,
    variant: str,
    repeat_index: int,
    judge: JudgeCompleter,
    judge_config: JudgeConfig,
):
    """Run one plan once through the frozen Evaluator. Only ``pair["input"]`` and
    one plan reach the Evaluator."""
    eval_id = f"{pair['pair_id']}__{variant}__r{repeat_index}"
    ctx = EvaluationRunContext(
        input_case_id=eval_id,
        generator_version=GENERATOR_VERSION,
        prompt_version=PROMPT_VERSION,
    )
    plan = pair["reference_plan"] if variant == "reference" else pair["degraded_plan"]
    raw = json.dumps(plan, ensure_ascii=False)
    return evaluate_speech_plan(pair["input"], raw, ctx, judge_config, judge)


def reduce_result(
    pair_id: str,
    variant: str,
    repeat_index: int,
    result,
) -> ConfirmatoryRecord:
    """Reduce one EvaluatorResult to a ConfirmatoryRecord. Never converts a
    failure into a semantic zero."""
    artifact = result.artifact
    if artifact is not None and artifact.structural_valid:
        scores = {d: artifact.scores[d].score for d in DIMENSION_IDS}
        flags = tuple(cf.flag for cf in artifact.critical_flags)
        return ConfirmatoryRecord(
            pair_id=pair_id, variant=variant, repeat_index=repeat_index,
            scores=scores, critical_flags=flags, failure_type=None,
        )
    if artifact is not None and not artifact.structural_valid:
        return ConfirmatoryRecord(
            pair_id=pair_id, variant=variant, repeat_index=repeat_index,
            scores=None, critical_flags=(),
            failure_type=f"gate_{artifact.gate_failure.stage}",
        )
    failure_type = result.failure.failure_type if result.failure is not None else "unknown"
    return ConfirmatoryRecord(
        pair_id=pair_id, variant=variant, repeat_index=repeat_index,
        scores=None, critical_flags=(), failure_type=failure_type,
    )


def execute_confirmatory_run(run: ConfirmatoryRun, judge: JudgeCompleter) -> None:
    """Execute the 144-call confirmatory run (real mode) and fill ``run``.

    The judge config is frozen-validated before the first call. Each call is a
    single independent attempt; there is no retry and no self-repair. Every raw
    UniversalEvaluationArtifact / EvaluatorFailureArtifact is captured verbatim.
    """
    judge_config = build_frozen_judge_config(judge)

    run.dry_run = False
    run.judge_provider = judge.provider
    run.judge_model_requested = judge.model

    records: list[ConfirmatoryRecord] = []
    raw_evaluations: list[dict] = []
    reported: set[str] = set()

    for pair in run.pairs:
        for variant in ("reference", "degraded"):
            plan = pair["reference_plan"] if variant == "reference" else pair["degraded_plan"]
            for repeat_index in range(1, run.repeats + 1):
                result = evaluate_one(pair, variant, repeat_index, judge, judge_config)

                artifact_dump = None
                failure_dump = None
                outcome: str
                if result.artifact is not None:
                    outcome = "artifact"
                    artifact_dump = result.artifact.model_dump(mode="json")
                    rm = result.artifact.run_metadata.judge_model_reported
                    if rm:
                        reported.add(rm)
                elif result.failure is not None:
                    outcome = "failure"
                    failure_dump = result.failure.model_dump(mode="json")
                else:  # pragma: no cover — defensive
                    outcome = "unknown"

                eval_id = f"{pair['pair_id']}__{variant}__r{repeat_index}"
                raw_evaluations.append(
                    {
                        "evaluation_id": eval_id,
                        "pair_id": pair["pair_id"],
                        "family": pair["family"],
                        "variant": variant,
                        "repeat_index": repeat_index,
                        "outcome": outcome,
                        "artifact": artifact_dump,
                        "failure": failure_dump,
                    }
                )
                records.append(
                    reduce_result(pair["pair_id"], variant, repeat_index, result)
                )

    run.records = tuple(records)
    run.raw_evaluations = raw_evaluations
    run.judge_model_reported = tuple(sorted(reported))
    run.completed_at = _canonical_utc_now()


# ---------------------------------------------------------------------------
# Aggregation (pure — delegates to protocol_v0_2 metrics).
# ---------------------------------------------------------------------------
def aggregate(run: ConfirmatoryRun) -> dict[str, Any]:
    """Compute all frozen v0.2 metrics over the run's records."""
    records = run.records
    pairs = run.pairs
    metadata = run.metadata
    return {
        "semantic": P.evaluate_semantic_validation(records, pairs, metadata),
        "operational": P.operational_reliability(records, EXPECTED_CALLS),
        "flags": P.confirmatory_flag_diagnostics(records, pairs),
        "collateral": P.collateral_diagnostics(records, pairs, metadata),
        "family_metrics": P.family_metrics(records, pairs, metadata),
    }


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------
def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_manifest(run: ConfirmatoryRun) -> dict[str, Any]:
    """Run-level manifest (Protocol v0.2 Section 25 + task Section 8). No secrets."""
    return {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dry_run": run.dry_run,
        "protocol_version": P.PROTOCOL_VERSION,
        "protocol_document_path": str(P.PROTOCOL_DOC_PATH),
        "protocol_document_sha256": run.protocol_document_sha256,
        "protocol_metadata_path": str(P.PROTOCOL_METADATA_PATH),
        "protocol_metadata_sha256": run.protocol_metadata_sha256,
        "freeze_record_path": str(P.FREEZE_RECORD_PATH),
        "freeze_record_status": run.freeze_record.get("status"),
        "dataset_path": run.dataset_path,
        "dataset_sha256": run.dataset_sha256,
        "confirmatory_dataset_path": run.dataset_path,
        "confirmatory_dataset_version": run.freeze_record.get("dataset_version"),
        "confirmatory_dataset_sha256": run.dataset_sha256,
        "development_dataset_path": str(P.DEVELOPMENT_DATASET_PATH),
        "development_dataset_sha256": P.DEVELOPMENT_DATASET_SHA256,
        "pair_count": len(run.pairs),
        "plan_count": len(run.pairs) * 2,
        "repeats": run.repeats,
        "expected_calls": EXPECTED_CALLS,
        "successful_evaluations": sum(1 for r in run.records if r.scores is not None),
        "failed_evaluations": sum(1 for r in run.records if r.scores is None),
        "evaluator_version": EVALUATOR_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": compute_judge_prompt_sha256(),
        "judge_provider": run.judge_provider or P.FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": run.judge_model_requested or P.FROZEN_JUDGE_MODEL_REQUESTED,
        "judge_model_reported": list(run.judge_model_reported),
        "temperature": P.FROZEN_TEMPERATURE,
        "structured_output_enabled": P.FROZEN_STRUCTURED_OUTPUT_ENABLED,
        "retry_enabled": P.FROZEN_RETRY_ENABLED,
        "self_repair_enabled": P.FROZEN_SELF_REPAIR_ENABLED,
    }


def build_summary(run: ConfirmatoryRun, agg: dict[str, Any]) -> dict[str, Any]:
    """Confirmatory summary.json with the six acceptance criteria + operational stats."""
    semantic = agg["semantic"]
    operational = agg["operational"]
    flags = agg["flags"]
    collateral = agg["collateral"]
    fam_metrics = agg["family_metrics"]

    def _crit(key: str, value: float, threshold: float, passed: bool, **extra) -> dict:
        d = {"value": value, "threshold": threshold, "pass": bool(passed)}
        d.update(extra)
        return d

    return {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "dataset_sha256": run.dataset_sha256,
        "protocol_version": P.PROTOCOL_VERSION,
        "judge_provider": run.judge_provider or P.FROZEN_JUDGE_PROVIDER,
        "judge_model_requested": run.judge_model_requested or P.FROZEN_JUDGE_MODEL_REQUESTED,
        "judge_model_reported": list(run.judge_model_reported),
        "semantic_validation": semantic.verdict,
        "acceptance_criteria": {
            "primary_directional_accuracy": _crit(
                "primary_directional_accuracy", semantic.primary_directional_accuracy.accuracy,
                P.PRIMARY_DIRECTIONAL_ACCURACY_THRESHOLD,
                semantic.primary_directional_accuracy.passed,
                numerator=semantic.primary_directional_accuracy.numerator,
                denominator=semantic.primary_directional_accuracy.denominator,
            ),
            "mean_primary_targeted_drop": _crit(
                "mean_primary_targeted_drop", semantic.mean_primary_targeted_drop.mean_drop,
                P.MEAN_PRIMARY_DROP_THRESHOLD, semantic.mean_primary_targeted_drop.passed,
                n=semantic.mean_primary_targeted_drop.n,
                n_at_least_one=semantic.mean_primary_targeted_drop.n_at_least_one,
                proportion_at_least_one=semantic.mean_primary_targeted_drop.proportion_at_least_one,
            ),
            "protected_dimension_mae": _crit(
                "protected_dimension_mae", semantic.protected_dimension_mae.mae,
                P.PROTECTED_MAE_THRESHOLD, semantic.protected_dimension_mae.passed,
                n_comparisons=semantic.protected_dimension_mae.n_comparisons,
                exact_zero_count=semantic.protected_dimension_mae.exact_zero_count,
                exact_zero_proportion=semantic.protected_dimension_mae.exact_zero_proportion,
            ),
            "within_one_repeatability": _crit(
                "within_one_repeatability", semantic.repeatability.within_one_agreement,
                P.WITHIN_ONE_REPEATABILITY_THRESHOLD, semantic.repeatability.passed,
                n_comparisons=semantic.repeatability.n_comparisons,
                exact_agreement=semantic.repeatability.exact_agreement,
                eligible_series=semantic.repeatability.eligible_series,
            ),
            "semantic_pair_coverage": _crit(
                "semantic_pair_coverage", semantic.semantic_pair_coverage.coverage,
                P.SEMANTIC_COVERAGE_THRESHOLD, semantic.semantic_pair_coverage.passed,
                numerator=semantic.semantic_pair_coverage.eligible,
                denominator=semantic.semantic_pair_coverage.total,
            ),
            "per_family_coverage": {
                "value": "every family >= 2/3 eligible",
                "pass": semantic.per_family_coverage_pass,
                "per_family": semantic.semantic_pair_coverage.per_family,
            },
        },
        "operational": {
            "expected_calls": operational.expected_calls,
            "successful_evaluations": operational.successful,
            "failed_evaluations": operational.failed,
            "operational_success_rate": operational.success_rate,
            "failure_counts": operational.failure_counts,
        },
        "family_coverage": semantic.semantic_pair_coverage.per_family,
        "family_metrics": fam_metrics,
        "collateral_diagnostics": {
            "global_mean_signed_drop": collateral.global_mean_signed,
            "global_mean_absolute_shift": collateral.global_mean_absolute,
            "per_dimension": collateral.per_dimension,
            "per_family": collateral.per_family,
        },
        "critical_flags": {
            "tp": flags.tp,
            "fn": flags.fn,
            "fp": flags.fp,
            "per_flag": flags.per_flag,
            "per_pair": flags.per_pair,
            "reference_side_flags": list(flags.reference_side_flags),
        },
    }


def write_artifacts(
    run: ConfirmatoryRun,
    out_dir: Path | str,
    *,
    agg: dict[str, Any] | None = None,
) -> None:
    """Write the confirmatory artifact set. ``agg`` is omitted in dry-run mode."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(out_dir / "run_manifest.json", build_manifest(run))

    if agg is not None:
        _write_json(out_dir / "summary.json", build_summary(run, agg))
        _write_family_metrics_csv(out_dir / "family_metrics.csv", agg["family_metrics"])
        _write_pair_metrics_csv(
            out_dir / "pair_metrics.csv", run.pairs, run.records, run.metadata
        )
    else:
        # Dry-run still writes a summary stub documenting the plan.
        _write_json(out_dir / "summary.json", {
            "run_id": run.run_id,
            "dry_run": True,
            "started_at": run.started_at,
            "dataset_sha256": run.dataset_sha256,
            "protocol_version": P.PROTOCOL_VERSION,
            "judge_provider": P.FROZEN_JUDGE_PROVIDER,
            "judge_model_requested": P.FROZEN_JUDGE_MODEL_REQUESTED,
            "expected_calls": EXPECTED_CALLS,
            "pair_count": len(run.pairs),
            "plan_count": len(run.pairs) * 2,
            "repeats": run.repeats,
            "semantic_validation": None,
        })

    if run.raw_evaluations:
        with (out_dir / "evaluations.jsonl").open("w", encoding="utf-8") as handle:
            for rec in run.raw_evaluations:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

    (out_dir / "README.md").write_text(_readme_text(run), encoding="utf-8")


def _write_pair_metrics_csv(
    path: Path, pairs: Sequence[dict], records: Sequence[ConfirmatoryRecord], metadata: dict
) -> None:
    header = (
        ["pair_id", "family", "eligible",
         "reference_success_count", "degraded_success_count"]
        + [f"{d}_{x}" for d in ("D1", "D2", "D3", "D4", "D5", "D6") for x in ("ref_mean", "deg_mean", "delta")]
        + ["primary_dimensions", "collateral_dimensions", "protected_dimensions",
           "expected_flags", "degraded_critical_flags", "reference_critical_flags"]
    )
    dim_map = {d: f"D{i+1}" for i, d in enumerate(DIMENSION_IDS)}

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for pair in pairs:
            pid = pair["pair_id"]
            part = P.family_partition(metadata, pair["family"])
            ref = P.variant_mean_scores(records, pid, "reference")
            deg = P.variant_mean_scores(records, pid, "degraded")
            ref_cnt = P.successful_repeat_count(records, pid, "reference")
            deg_cnt = P.successful_repeat_count(records, pid, "degraded")
            eligible = P.pair_eligible(records, pid)

            row = [pid, pair["family"], eligible, ref_cnt, deg_cnt]
            for d in DIMENSION_IDS:
                rv = ref[d] if ref is not None else ""
                dv = deg[d] if deg is not None else ""
                delta = round(rv - dv, 4) if (ref is not None and deg is not None) else ""
                row += [rv, dv, delta]

            deg_flags = sorted({
                f for r in P._successful_records(records, pid, "degraded")
                for f in r.critical_flags
            })
            ref_flags = sorted({
                f for r in P._successful_records(records, pid, "reference")
                for f in r.critical_flags
            })
            row += [
                "|".join(part.primary),
                "|".join(part.collateral),
                "|".join(part.protected),
                "|".join(pair["expected_flags"]),
                "|".join(deg_flags),
                "|".join(ref_flags),
            ]
            writer.writerow(row)


def _write_family_metrics_csv(path: Path, fam_metrics: dict[str, dict]) -> None:
    header = [
        "family", "total_pairs", "eligible_pairs",
        "directional_numerator", "directional_denominator", "directional_accuracy",
        "mean_primary_targeted_drop", "protected_dimension_mae",
        "collateral_mean_signed_drop", "collateral_mean_absolute_shift",
        "repeatability_within_one", "flag_tp", "flag_fn", "flag_fp",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for fam in P.DIAGNOSTIC_FAMILIES:
            m = fam_metrics[fam]
            writer.writerow([
                fam, m["total_pairs"], m["eligible_pairs"],
                m["primary_directional_accuracy"]["numerator"],
                m["primary_directional_accuracy"]["denominator"],
                m["primary_directional_accuracy"]["accuracy"],
                m["mean_primary_targeted_drop"],
                m["protected_dimension_mae"],
                m["collateral_mean_signed_drop"],
                m["collateral_mean_absolute_shift"],
                m["repeatability_within_one"],
                m["critical_flags"]["tp"],
                m["critical_flags"]["fn"],
                m["critical_flags"]["fp"],
            ])


def _readme_text(run: ConfirmatoryRun) -> str:
    lines = [
        "# TeachIntent Evaluator Diagnostic Protocol v0.2 — Confirmatory Run",
        "",
        f"- run_id: {run.run_id}",
        f"- started_at: {run.started_at}",
        f"- completed_at: {run.completed_at}",
        f"- dry_run: {run.dry_run}",
        f"- protocol_version: {P.PROTOCOL_VERSION}",
        f"- dataset: {run.dataset_path}",
        f"- dataset_sha256: {run.dataset_sha256}",
        f"- protocol_metadata_sha256: {run.protocol_metadata_sha256}",
        f"- protocol_document_sha256: {run.protocol_document_sha256}",
        f"- freeze_record_status: {run.freeze_record.get('status')}",
        f"- pairs: {len(run.pairs)} / plans: {len(run.pairs) * 2} / repeats: {run.repeats}",
        f"- expected calls: {EXPECTED_CALLS}",
        f"- evaluator_version: {EVALUATOR_VERSION}",
        f"- judge_prompt_version: {JUDGE_PROMPT_VERSION}",
        f"- judge_provider: {P.FROZEN_JUDGE_PROVIDER}",
        f"- judge_model_requested: {P.FROZEN_JUDGE_MODEL_REQUESTED}",
        "",
        "Artifacts: run_manifest.json / summary.json / evaluations.jsonl /",
        "pair_metrics.csv / family_metrics.csv.",
        "",
        "This directory is git-ignored (results/). Do not commit.",
    ]
    if run.judge_model_reported:
        lines.append(f"- judge_model_reported: {sorted(run.judge_model_reported)}")
    return "\n".join(lines) + "\n"
