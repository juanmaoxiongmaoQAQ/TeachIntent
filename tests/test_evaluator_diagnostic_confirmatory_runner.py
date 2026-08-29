"""Offline tests for the Protocol v0.2 confirmatory runner.

Covers: exact 144-call planning, dataset SHA fail-fast, frozen judge config
binding, experiment-metadata isolation from the Judge payload, artifact schema
/ JSON serialization, and the frozen manifest fields. No API calls.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from teachintent.evaluator import JudgeCompletion
from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.evaluator_diagnostic import (
    CONFIRMATORY_DATASET_PATH,
    CONFIRMATORY_DATASET_SHA256,
    EXPECTED_CALLS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    FROZEN_RETRY_ENABLED,
    FROZEN_SELF_REPAIR_ENABLED,
    FROZEN_STRUCTURED_OUTPUT_ENABLED,
    ConfirmatoryRecord,
    DatasetIntegrityError,
    aggregate,
    build_frozen_judge_config,
    build_manifest,
    build_summary,
    evaluate_one,
    family_partition,
    load_diagnostic_pairs,
    plan_confirmatory_calls,
    prepare_confirmatory_run,
    write_artifacts,
)

D = DIMENSION_IDS


def _scores(**ov) -> dict[str, int]:
    b = {d: 4 for d in D}
    b.update(ov)
    return b


def _perfect_records(pairs, metadata) -> list[ConfirmatoryRecord]:
    records = []
    for p in pairs:
        part = family_partition(metadata, p["family"])
        for variant in ("reference", "degraded"):
            for repeat in range(1, 4):
                s = {}
                for d in D:
                    if d in part.primary:
                        s[d] = 4 if variant == "reference" else 1
                    elif d in part.collateral:
                        s[d] = 4 if variant == "reference" else 2
                    else:
                        s[d] = 4
                records.append(ConfirmatoryRecord(
                    pair_id=p["pair_id"], variant=variant, repeat_index=repeat, scores=s))
    return records


def _valid_output() -> str:
    return json.dumps({
        "scores": {
            d: {"score": 4,
                "evidence": [{"source": "plan.verbal_plan.segments[0].text", "text": "x"}],
                "brief_justification": "ok"}
            for d in D
        },
        "critical_flags": [],
    }, ensure_ascii=False)


class CapturingJudge:
    def __init__(self, model=FROZEN_JUDGE_MODEL_REQUESTED, provider=FROZEN_JUDGE_PROVIDER):
        self._model = model
        self._provider = provider
        self.systems: list[str] = []
        self.users: list[str] = []

    @property
    def provider(self):
        return self._provider

    @property
    def model(self):
        return self._model

    @property
    def structured_output_enabled(self):
        return False

    def complete(self, system, user, *, temperature=0.0):
        self.systems.append(system)
        self.users.append(user)
        return JudgeCompletion(
            content=_valid_output(), reported_model=self._model,
            structured_object=None, finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# 1. Exact 24 x 2 x 3 call planning.
# ---------------------------------------------------------------------------
def test_plan_144_calls():
    run = prepare_confirmatory_run()
    calls = plan_confirmatory_calls(run.pairs, 3)
    assert len(calls) == EXPECTED_CALLS == 144
    assert len({c["pair_id"] for c in calls}) == 24
    assert {c["variant"] for c in calls} == {"reference", "degraded"}
    assert {c["repeat_index"] for c in calls} == {1, 2, 3}
    pv = Counter((c["pair_id"], c["variant"]) for c in calls)
    assert len(pv) == 48
    assert all(n == 3 for n in pv.values())
    # file order: reference before degraded, repeats in order.
    first = calls[0]
    assert first == {"pair_id": "HOLDOUT-A-01", "family": "intent_mismatch",
                     "variant": "reference", "repeat_index": 1}
    assert run.planned_calls == 144


# ---------------------------------------------------------------------------
# 2. Dataset SHA mismatch fail-fast.
# ---------------------------------------------------------------------------
def test_dataset_sha_mismatch_fail_fast(tmp_path):
    dst = tmp_path / "tampered.jsonl"
    shutil.copy(CONFIRMATORY_DATASET_PATH, dst)
    with dst.open("a", encoding="utf-8") as f:
        f.write('{"pair_id": "TAMPERED"}\n')  # valid JSON, changes SHA
    with pytest.raises(DatasetIntegrityError):
        prepare_confirmatory_run(dst)


def test_dataset_integrity_ok_for_frozen_dataset():
    run = prepare_confirmatory_run()
    assert run.integrity.ok is True
    assert run.dataset_sha256 == CONFIRMATORY_DATASET_SHA256
    assert len(run.pairs) == 24
    assert run.freeze_record.get("status") == "Frozen"


# ---------------------------------------------------------------------------
# 3. Family partition lookup (via runner path).
# ---------------------------------------------------------------------------
def test_metadata_partition_lookup_via_runner():
    run = prepare_confirmatory_run()
    a = family_partition(run.metadata, "intent_mismatch")
    assert a.primary == ("pedagogical_intent_fidelity",)
    assert a.collateral == ("intent_specific_instructional_adequacy",)
    assert len(a.protected) == 4


# ---------------------------------------------------------------------------
# 4. Experiment metadata never reaches the Judge payload.
# ---------------------------------------------------------------------------
def test_experiment_metadata_not_in_judge_payload():
    pair = load_diagnostic_pairs(CONFIRMATORY_DATASET_PATH)[0]
    judge = CapturingJudge()
    cfg = build_frozen_judge_config(judge)
    evaluate_one(pair, "reference", 1, judge, cfg)

    assert len(judge.systems) == 1 and len(judge.users) == 1
    combined = judge.systems[0] + "\n" + judge.users[0]

    # Experiment metadata MUST NOT appear.
    assert "HOLDOUT-" not in combined          # pair_id / eval_id
    assert pair["family"] not in combined      # family label
    assert "expected_flags" not in combined
    assert "primary_target_dimensions" not in combined
    assert "allowed_collateral_dimensions" not in combined
    assert "protected_dimensions" not in combined
    assert "dataset_sha256" not in combined
    assert "protocol_v0.2" not in combined
    # The pair's notes text must not leak either.
    if pair.get("notes"):
        assert pair["notes"] not in combined

    # Layer-1-visible content SHOULD appear.
    anchor = pair["input"]["instructional_content"]["content_anchor"]
    assert anchor in combined
    seg_text = pair["reference_plan"]["verbal_plan"]["segments"][0]["text"]
    assert seg_text in combined


# ---------------------------------------------------------------------------
# 34. Judge model exact requested id + provider.
# ---------------------------------------------------------------------------
def test_judge_model_exact_requested_id():
    assert FROZEN_JUDGE_MODEL_REQUESTED == "qwen/qwen3.5-plus-20260420"
    assert FROZEN_JUDGE_PROVIDER == "openrouter"
    with pytest.raises(ValueError, match="model mismatch"):
        build_frozen_judge_config(CapturingJudge(model="tencent/hy3"))
    with pytest.raises(ValueError, match="provider mismatch"):
        build_frozen_judge_config(CapturingJudge(provider="other"))
    cfg = build_frozen_judge_config(CapturingJudge())
    assert cfg.judge_model_requested == "qwen/qwen3.5-plus-20260420"
    assert cfg.judge_provider == "openrouter"


# ---------------------------------------------------------------------------
# 35. retry / self-repair / structured-output remain false.
# ---------------------------------------------------------------------------
def test_retry_self_repair_false():
    cfg = build_frozen_judge_config(CapturingJudge())
    assert cfg.retry_enabled is False
    assert cfg.self_repair_enabled is False
    assert cfg.structured_output_enabled is False
    assert cfg.temperature == 0
    assert FROZEN_RETRY_ENABLED is False
    assert FROZEN_SELF_REPAIR_ENABLED is False
    assert FROZEN_STRUCTURED_OUTPUT_ENABLED is False


def test_structured_output_enabled_backend_rejected():
    class StructuredJudge(CapturingJudge):
        @property
        def structured_output_enabled(self):
            return True
    with pytest.raises(ValueError, match="structured_output"):
        build_frozen_judge_config(StructuredJudge())


# ---------------------------------------------------------------------------
# 32/33. Artifact schemas + frozen SHA in manifest.
# ---------------------------------------------------------------------------
def test_manifest_contains_frozen_dataset_sha():
    run = prepare_confirmatory_run()
    m = build_manifest(run)
    assert m["confirmatory_dataset_sha256"] == CONFIRMATORY_DATASET_SHA256
    assert m["confirmatory_dataset_sha256"] == (
        "f14e2a87c7a62345963d389441388c4f74a91b9b5bb00457ed580da285420569"
    )
    assert m["development_dataset_sha256"] == (
        "a004715338c97d9e85b92fe0221a18631aa2884f6bb8b1d78a66066ccdd12664"
    )
    assert m["expected_calls"] == 144


def test_artifact_json_serialization():
    run = prepare_confirmatory_run()
    m = build_manifest(run)
    json.dumps(m, ensure_ascii=False)  # must not raise
    for key in ("run_id", "started_at", "dataset_path", "dataset_sha256",
                "protocol_version", "protocol_metadata_sha256",
                "protocol_document_sha256", "freeze_record_path",
                "judge_prompt_version", "judge_prompt_sha256", "judge_provider",
                "judge_model_requested", "temperature", "structured_output_enabled",
                "retry_enabled", "self_repair_enabled", "pair_count", "repeats",
                "expected_calls"):
        assert key in m, key


def test_summary_has_six_acceptance_criteria():
    run = prepare_confirmatory_run()
    run.records = tuple(_perfect_records(run.pairs, run.metadata))
    run.dry_run = False
    agg = aggregate(run)
    summary = build_summary(run, agg)
    json.dumps(summary, ensure_ascii=False)
    assert summary["semantic_validation"] == "PASS"
    criteria = summary["acceptance_criteria"]
    assert set(criteria.keys()) == {
        "primary_directional_accuracy",
        "mean_primary_targeted_drop",
        "protected_dimension_mae",
        "within_one_repeatability",
        "semantic_pair_coverage",
        "per_family_coverage",
    }
    assert criteria["primary_directional_accuracy"]["numerator"] == 24
    assert criteria["primary_directional_accuracy"]["denominator"] == 24
    assert criteria["primary_directional_accuracy"]["pass"] is True
    assert "operational" in summary
    assert "critical_flags" in summary
    assert "family_metrics" in summary


def test_write_artifacts_dry_run(tmp_path):
    run = prepare_confirmatory_run()
    out = tmp_path / "out"
    write_artifacts(run, out, agg=None)
    assert (out / "run_manifest.json").exists()
    assert (out / "summary.json").exists()
    assert (out / "README.md").exists()


def test_write_artifacts_with_metrics(tmp_path):
    run = prepare_confirmatory_run()
    run.records = tuple(_perfect_records(run.pairs, run.metadata))
    run.dry_run = False
    agg = aggregate(run)
    out = tmp_path / "out"
    write_artifacts(run, out, agg=agg)
    assert (out / "summary.json").exists()
    assert (out / "pair_metrics.csv").exists()
    assert (out / "family_metrics.csv").exists()
    # No API key anywhere in any artifact.
    blob = "".join(p.read_text(encoding="utf-8") for p in out.iterdir()
                   if p.suffix in (".json", ".csv", ".md"))
    assert "OPENROUTER_API_KEY" not in blob
    assert "api_key" not in blob
