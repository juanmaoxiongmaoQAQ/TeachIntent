"""Offline tests for the Generator v0.1 Baseline Evaluation runner.

Covers: canonical-run loading (12/12/6 = 30, unique ids, restorability), exact
90-call planning with repeat labels {1,2,3}, case eligibility, deterministic
aggregation (global / intent / block / case diagnostics), strict-majority
critical flags, artifact schemas, and frozen judge-config binding.

No Judge API call is ever made: all execution tests use a scripted offline
judge that returns precomputed, evidence-grounded responses.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from teachintent.evaluator import JudgeCompletion
from teachintent.evaluator.errors import JudgeAPIError
from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.generator_evaluation import (
    BLOCK_NAMES,
    CANONICAL_RUNS,
    CASE_COUNT,
    EXPECTED_CALLS,
    FROZEN_JUDGE_MODEL_REQUESTED,
    FROZEN_JUDGE_PROVIDER,
    FROZEN_RETRY_ENABLED,
    FROZEN_SELF_REPAIR_ENABLED,
    FROZEN_STRUCTURED_OUTPUT_ENABLED,
    GENERATOR_VERSION,
    GENERATOR_VERSION_PROVENANCE,
    INTENTS,
    MIN_SUCCESSFUL_REPEATS,
    POPULATION_HASH_ARTIFACTS,
    PROMPT_VERSION,
    PROTOCOL_STATUS,
    PROTOCOL_VERSION,
    REPEATS,
    SEVERE_WEAKNESS_THRESHOLD,
    SOURCE_POPULATION_SHA256,
    WEAKNESS_THRESHOLD,
    BaselineRecord,
    CanonicalCase,
    CanonicalRunError,
    CanonicalRunSpec,
    aggregate,
    block_metrics,
    build_baseline_judge,
    build_frozen_judge_config,
    build_manifest,
    build_population_records,
    build_summary,
    case_critical_flags,
    case_diagnostics,
    case_dimension_means,
    case_eligible,
    case_failure_types,
    case_overall_mean,
    compute_population_sha256,
    critical_flag_counts,
    evaluate_one,
    execute_baseline_run,
    failure_taxonomy_counts,
    global_metrics,
    intent_metrics,
    load_canonical_cases,
    plan_baseline_calls,
    prepare_baseline_run,
    successful_repeat_count,
    verify_population,
    verify_population_fingerprint,
    write_artifacts,
)
from teachintent.evaluator import compute_overall_score

D = DIMENSION_IDS


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
def _scores(value: int = 4, **overrides: int) -> dict[str, int]:
    base = {d: value for d in D}
    base.update(overrides)
    return base


def _rec(
    case_id: str,
    repeat_index: int,
    scores: dict[str, int] | None = None,
    *,
    flags: tuple[str, ...] = (),
    failure: str | None = None,
    block: str = "A",
    intent: str = "elicitation",
) -> BaselineRecord:
    return BaselineRecord(
        case_id=case_id,
        block=block,
        intent=intent,
        repeat_index=repeat_index,
        scores=scores,
        overall_score=None if scores is None else compute_overall_score(scores),
        critical_flags=flags,
        failure_type=failure,
    )


def _case(case_id: str, block: str = "A", intent: str = "elicitation") -> CanonicalCase:
    return CanonicalCase(
        case_id=case_id,
        block=block,
        block_name=BLOCK_NAMES[block],
        intent=intent,
        source_run_id="test-run",
        source_path="",
        input_doc={},
        raw_response="",
        prompt_version=PROMPT_VERSION,
        generator_version=GENERATOR_VERSION,
        requested_model=None,
        reported_model=None,
        generation_outcome="success",
    )


def _canonical_plan_doc(case: CanonicalCase) -> dict:
    return json.loads(case.raw_response)


def _grounded_text(plan_doc: dict) -> str:
    """A 40-char prefix of the plan's canonical JSON — always a grounded
    substring for object-valued evidence sources."""
    return json.dumps(
        plan_doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )[:40]


def _judge_payload(
    scores: dict[str, int], plan_doc: dict, flags: tuple[str, ...] = ()
) -> str:
    """Build a valid, evidence-grounded JudgeOutput JSON payload (offline)."""
    evidence_text = _grounded_text(plan_doc)
    return json.dumps(
        {
            "scores": {
                d: {
                    "score": scores[d],
                    "evidence": [{"source": "plan", "text": evidence_text}],
                    "brief_justification": "ok",
                }
                for d in D
            },
            "critical_flags": [
                {
                    "flag": flag,
                    "evidence": [{"source": "plan", "text": evidence_text}],
                    "brief_justification": "bad",
                }
                for flag in flags
            ],
        },
        ensure_ascii=False,
    )


class ScriptedJudge:
    """Deterministic offline judge: one precomputed response per call, in order.

    A response may be an ``Exception`` instance, which is raised instead (used
    to simulate operational failures without any network access).
    """

    provider = FROZEN_JUDGE_PROVIDER
    model = FROZEN_JUDGE_MODEL_REQUESTED
    structured_output_enabled = False

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.systems: list[str] = []
        self.users: list[str] = []

    def complete(self, system, user, *, temperature=0.0):
        index = self.calls
        self.calls += 1
        self.systems.append(system)
        self.users.append(user)
        response = self._responses[index]
        if isinstance(response, BaseException):
            raise response
        return JudgeCompletion(
            content=response,
            reported_model=self.model,
            structured_object=None,
            finish_reason="stop",
        )


def _build_responses(
    cases,
    *,
    repeats: int = REPEATS,
    failures: dict[str, set[int]] | None = None,
    score_fn=None,
    flags: tuple[str, ...] = (),
) -> list:
    responses: list = []
    for case in cases:
        plan_doc = _canonical_plan_doc(case)
        scores = score_fn(case) if score_fn is not None else _scores()
        for repeat in range(1, repeats + 1):
            if failures and repeat in failures.get(case.case_id, set()):
                responses.append(JudgeAPIError("simulated offline judge failure"))
            else:
                responses.append(_judge_payload(scores, plan_doc, flags))
    return responses


def _copy_run(tmp_path: Path, spec: CanonicalRunSpec, name: str = "run") -> Path:
    """Copy a real canonical run into tmp_path so tampering is safe."""
    dst = tmp_path / name
    shutil.copytree(spec.path, dst)
    return dst


def _tampered_spec(tmp_path: Path, spec: CanonicalRunSpec, name: str = "run") -> CanonicalRunSpec:
    dst = _copy_run(tmp_path, spec, name)
    return CanonicalRunSpec(
        block=spec.block,
        block_name=spec.block_name,
        run_id=spec.run_id,
        path=dst,
        expected_cases=spec.expected_cases,
    )


# ---------------------------------------------------------------------------
# 1. Canonical population: existence, counts, uniqueness, restorability.
# ---------------------------------------------------------------------------
def test_canonical_run_registry_ids_and_paths():
    assert [s.block for s in CANONICAL_RUNS] == ["A", "B", "C"]
    assert [s.run_id for s in CANONICAL_RUNS] == [
        "20260827-002543",
        "20260827-051547",
        "20260827-074602",
    ]
    assert [s.expected_cases for s in CANONICAL_RUNS] == [12, 12, 6]
    assert BLOCK_NAMES == {
        "A": "controlled_contrast",
        "B": "cross_domain_generalization",
        "C": "hard_adversarial",
    }
    for spec in CANONICAL_RUNS:
        assert spec.path.is_dir(), spec.path
        assert (spec.path / "manifest.json").is_file()
        assert (spec.path / "cases").is_dir()


def test_canonical_counts_are_12_12_6_total_30():
    cases, integrity = load_canonical_cases()
    assert integrity.per_block_counts == {"A": 12, "B": 12, "C": 6}
    assert len(cases) == CASE_COUNT == 30
    assert sum(integrity.per_block_counts.values()) == 30


def test_case_ids_are_unique():
    cases, integrity = load_canonical_cases()
    ids = [c.case_id for c in cases]
    assert len(set(ids)) == len(ids) == 30
    assert integrity.unique_case_ids is True
    assert integrity.duplicate_case_ids == []


def test_every_case_is_restorable():
    cases, integrity = load_canonical_cases()
    assert integrity.restorable_cases == 30
    for case in cases:
        # validated input
        assert case.input_doc["pedagogical_intent"]["primary"] in INTENTS
        # raw Generator response / generated Speech Plan
        assert case.raw_response.strip()
        plan = _canonical_plan_doc(case)
        assert "verbal_plan" in plan
        # versions
        assert case.generator_version == "v0.1"
        assert case.prompt_version == "v0.1"
        # canonical generation succeeded
        assert case.generation_outcome == "success"


def test_generator_and_prompt_versions_are_v0_1():
    cases, integrity = load_canonical_cases()
    assert integrity.prompt_versions == ["v0.1"]
    assert integrity.generation_outcomes == ["success"]
    assert GENERATOR_VERSION == "v0.1"
    assert PROMPT_VERSION == "v0.1"
    assert {c.generator_version for c in cases} == {"v0.1"}


def test_intent_distribution_covers_six_intents():
    cases, _ = load_canonical_cases()
    counts = Counter(c.intent for c in cases)
    assert set(counts) == set(INTENTS)
    assert sum(counts.values()) == 30


# ---------------------------------------------------------------------------
# 2. Population integrity fail-fast (offline tampering).
# ---------------------------------------------------------------------------
def test_wrong_block_count_fails_fast(tmp_path):
    spec = _tampered_spec(tmp_path, CANONICAL_RUNS[2])  # block C: 6 cases
    shutil.rmtree(spec.path / "cases" / "PILOT-C-EXT-01")
    with pytest.raises(CanonicalRunError, match="expected 6 cases"):
        load_canonical_cases([spec])


def test_wrong_prompt_version_fails_fast(tmp_path):
    spec = _tampered_spec(tmp_path, CANONICAL_RUNS[2])
    case_dir = spec.path / "cases" / "PILOT-C-ELI-01"
    for name in ("metadata.json", "prompt.json"):
        path = case_dir / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["prompt_version"] = "v0.2"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(CanonicalRunError, match="prompt_version"):
        load_canonical_cases([spec])


def test_unrestorable_raw_response_fails_fast(tmp_path):
    spec = _tampered_spec(tmp_path, CANONICAL_RUNS[2])
    (spec.path / "cases" / "PILOT-C-ELI-01" / "raw_response.txt").write_text(
        "not json at all", encoding="utf-8"
    )
    with pytest.raises(CanonicalRunError, match="not restorable"):
        load_canonical_cases([spec])


def test_verify_population_detects_duplicates():
    cases = [_case("X-01"), _case("X-01"), _case("X-02")]
    report = verify_population(cases)
    assert report.ok is False
    assert report.unique_case_ids is False
    assert report.duplicate_case_ids == ["X-01"]


def test_verify_population_ok_for_full_population():
    cases = (
        [_case(f"A-{i:02d}", block="A") for i in range(1, 13)]
        + [_case(f"B-{i:02d}", block="B") for i in range(1, 13)]
        + [_case(f"C-{i:02d}", block="C") for i in range(1, 7)]
    )
    report = verify_population(cases)
    assert report.ok is True
    assert report.messages == []
    assert report.per_block_counts == {"A": 12, "B": 12, "C": 6}
    assert report.total_cases == 30


def test_verify_population_requires_the_full_30_case_population():
    cases = [_case(f"C-{i:02d}", block="C") for i in range(1, 7)]
    report = verify_population(cases, [CANONICAL_RUNS[2]])
    assert report.ok is False
    assert any("expected 30 cases" in m for m in report.messages)
    assert report.per_block_counts == {"C": 6}


# ---------------------------------------------------------------------------
# 2b. Population fingerprint (SHA256 over the six raw source artifacts).
# ---------------------------------------------------------------------------
def test_population_fingerprint_matches_the_frozen_digest():
    cases, integrity = load_canonical_cases()
    assert integrity.population_sha256 == SOURCE_POPULATION_SHA256
    assert integrity.population_sha256_match is True
    digest, matches = verify_population_fingerprint(cases)
    assert digest == SOURCE_POPULATION_SHA256
    assert matches is True


def test_population_fingerprint_shape_and_determinism():
    cases, _ = load_canonical_cases()
    records = build_population_records(cases)
    assert len(records) == 30
    # Deterministic order: sorted by case_id.
    assert [r["case_id"] for r in records] == sorted(r["case_id"] for r in records)
    expected_keys = {
        "block",
        "source_run_id",
        "case_id",
        *{f"{k}_sha256" for k in POPULATION_HASH_ARTIFACTS},
    }
    for rec in records:
        assert set(rec) == expected_keys
        # every artifact hash is a full lowercase sha256 hex digest
        for key in POPULATION_HASH_ARTIFACTS:
            digest = rec[f"{key}_sha256"]
            assert len(digest) == 64
            assert digest == digest.lower()
            assert int(digest, 16) >= 0
    # Recomputation is stable (no dict-ordering / timestamp dependence).
    assert compute_population_sha256(build_population_records(cases)) == (
        compute_population_sha256(build_population_records(cases))
    )


def test_population_fingerprint_uses_the_canonical_serialization():
    cases, _ = load_canonical_cases()
    records = build_population_records(cases)
    canonical = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == (
        SOURCE_POPULATION_SHA256
    )


def test_tampering_any_source_artifact_fails_fast(tmp_path):
    """Editing a single byte of one canonical artifact aborts the run."""
    spec = _tampered_spec(tmp_path, CANONICAL_RUNS[2])
    path = spec.path / "cases" / "PILOT-C-ELI-01" / "raw_response.txt"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(CanonicalRunError, match="source population SHA256 mismatch"):
        load_canonical_cases([spec])


def test_tampering_a_non_scored_artifact_also_fails_fast(tmp_path):
    """The fingerprint covers metadata too, not only the scored artifacts."""
    spec = _tampered_spec(tmp_path, CANONICAL_RUNS[2])
    path = spec.path / "cases" / "PILOT-C-ELI-01" / "metadata.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["case_id"] = "PILOT-C-ELI-01"  # unchanged value — content rewrite only
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=4), encoding="utf-8")
    with pytest.raises(CanonicalRunError, match="source population SHA256 mismatch"):
        load_canonical_cases([spec])


def test_prepare_run_carries_the_fingerprint_and_provenance():
    run = prepare_baseline_run()
    assert run.protocol_status == PROTOCOL_STATUS == "Frozen"
    assert run.source_population_sha256 == SOURCE_POPULATION_SHA256
    assert run.source_population_sha256_match is True
    assert run.generator_version == "v0.1"
    assert "do not directly record generator_version" in (
        run.generator_version_provenance
    )
    assert run.prompt_version == "v0.1"
    assert "artifact_directly_recorded" in run.prompt_version_provenance
    assert GENERATOR_VERSION_PROVENANCE == (
        "inferred_from_frozen_generator_stack_and_prompt_v0.1; source Pilot "
        "artifacts do not directly record generator_version"
    )


def test_manifest_records_the_fingerprint_and_provenance():
    run = prepare_baseline_run()
    manifest = build_manifest(run)
    assert manifest["protocol_status"] == "Frozen"
    assert manifest["source_population_sha256"] == SOURCE_POPULATION_SHA256
    assert manifest["source_population_sha256_expected"] == SOURCE_POPULATION_SHA256
    assert manifest["source_population_sha256_match"] is True
    assert manifest["generator_version_provenance"] == GENERATOR_VERSION_PROVENANCE
    assert "prompt_version_provenance" in manifest
    records = manifest["source_population_records"]
    assert len(records) == 30
    assert {r["case_id"] for r in records} == {c.case_id for c in run.cases}


# ---------------------------------------------------------------------------
# 3. Exact 30 x 3 = 90 call planning, repeat labels {1,2,3}.
# ---------------------------------------------------------------------------
def test_plan_90_calls():
    run = prepare_baseline_run()
    calls = plan_baseline_calls(run.cases, 3)
    assert len(calls) == EXPECTED_CALLS == 90
    assert run.planned_calls == 90
    assert len({c["case_id"] for c in calls}) == 30


def test_plan_repeat_labels_are_1_2_3():
    run = prepare_baseline_run()
    calls = plan_baseline_calls(run.cases, 3)
    assert {c["repeat_index"] for c in calls} == {1, 2, 3}
    per_case = Counter(c["case_id"] for c in calls)
    assert len(per_case) == 30
    assert all(n == 3 for n in per_case.values())
    for case_id in per_case:
        repeats = sorted(
            c["repeat_index"] for c in calls if c["case_id"] == case_id
        )
        assert repeats == [1, 2, 3]
    # deterministic order: blocks A, B, C; within a block sorted by case_id.
    first = calls[0]
    assert first["case_id"] == "PILOT-A-COR-01"
    assert first["repeat_index"] == 1
    assert calls[-1]["case_id"] == "PILOT-C-SUP-01"
    assert calls[-1]["repeat_index"] == 3


def test_prepare_rejects_repeats_other_than_3():
    with pytest.raises(ValueError, match="repeats must be exactly 3"):
        prepare_baseline_run(repeats=2)
    with pytest.raises(ValueError, match="repeats must be exactly 3"):
        prepare_baseline_run(repeats=5)


def test_plan_rejects_repeats_below_one():
    with pytest.raises(ValueError, match="repeats must be >= 1"):
        plan_baseline_calls([_case("X")], 0)


def test_manifest_records_source_runs_and_design():
    run = prepare_baseline_run()
    manifest = build_manifest(run)
    assert json.dumps(manifest, ensure_ascii=False)
    assert [s["run_id"] for s in manifest["source_runs"]] == [
        "20260827-002543",
        "20260827-051547",
        "20260827-074602",
    ]
    assert manifest["source_run_ids"] == [
        "20260827-002543",
        "20260827-051547",
        "20260827-074602",
    ]
    assert manifest["per_block_case_counts"] == {"A": 12, "B": 12, "C": 6}
    assert manifest["unique_case_ids"] is True
    assert manifest["case_count"] == 30
    assert manifest["repeats"] == 3
    assert manifest["expected_calls"] == 90
    assert manifest["planned_calls"] == 90
    assert manifest["generator_version"] == "v0.1"
    assert manifest["prompt_version"] == "v0.1"
    assert manifest["evaluator_version"] == "v0.1"
    assert manifest["judge_prompt_version"] == "v0.1"
    assert manifest["judge_provider"] == "openrouter"
    assert manifest["judge_model_requested"] == "qwen/qwen3.5-plus-20260420"
    assert manifest["temperature"] == 0
    assert manifest["structured_output_enabled"] is False
    assert manifest["retry_enabled"] is False
    assert manifest["self_repair_enabled"] is False
    assert len(manifest["case_ids"]) == 30
    assert "started_at" in manifest and "completed_at" in manifest


# ---------------------------------------------------------------------------
# 4. Eligibility + aggregation (synthetic records, no API).
# ---------------------------------------------------------------------------
def test_case_eligibility_thresholds():
    records = [
        _rec("c", 1, _scores()),
        _rec("c", 2, _scores()),
        _rec("c", 3, _scores()),
    ]
    assert successful_repeat_count(records, "c") == 3
    assert case_eligible(records, "c") is True

    two = [r for r in records if r.repeat_index != 3]
    assert case_eligible(two, "c") is True  # 2/3 -> eligible

    one = [records[0]]
    assert case_eligible(one, "c") is False  # 1/3 -> excluded

    assert case_eligible([], "c") is False  # 0/3 -> excluded
    assert MIN_SUCCESSFUL_REPEATS == 2


def test_case_dimension_means_ignore_failed_repeats():
    records = [
        _rec("c", 1, _scores(4, **{D[0]: 2})),
        _rec("c", 2, _scores(4, **{D[0]: 4})),
        _rec("c", 3, None, failure="judge_api_error"),
    ]
    means = case_dimension_means(records, "c")
    assert means[D[0]] == 3.0  # mean of 2 and 4, failure not imputed as 0
    assert means[D[1]] == 4.0
    # overall mean averages only the two successful repeats.
    assert case_overall_mean(records, "c") == (
        round((compute_overall_score(records[0].scores)
               + compute_overall_score(records[1].scores)) / 2, 4)
    )


def test_failure_is_never_converted_to_zero():
    records = [_rec("c", 1, None, failure="judge_api_error")]
    assert case_dimension_means(records, "c") is None
    assert case_overall_mean(records, "c") is None
    assert case_eligible(records, "c") is False
    assert case_critical_flags(records, "c") == ()


def test_case_critical_flags_strict_majority():
    flag = "learner_humiliation"
    # 2 of 3 -> raised
    recs = [
        _rec("c", 1, _scores(), flags=(flag,)),
        _rec("c", 2, _scores(), flags=(flag,)),
        _rec("c", 3, _scores()),
    ]
    assert case_critical_flags(recs, "c") == (flag,)
    # 1 of 3 -> NOT raised
    recs = [
        _rec("c", 1, _scores(), flags=(flag,)),
        _rec("c", 2, _scores()),
        _rec("c", 3, _scores()),
    ]
    assert case_critical_flags(recs, "c") == ()
    # 2 of 2 -> raised
    recs = [
        _rec("c", 1, _scores(), flags=(flag,)),
        _rec("c", 2, _scores(), flags=(flag,)),
    ]
    assert case_critical_flags(recs, "c") == (flag,)
    # 1 of 2 -> NOT raised (strict majority)
    recs = [
        _rec("c", 1, _scores(), flags=(flag,)),
        _rec("c", 2, _scores()),
    ]
    assert case_critical_flags(recs, "c") == ()
    # failed repeats contribute neither evidence nor denominator; a case with
    # fewer than 2 successful repeats is excluded and reports no case-level flag
    recs = [
        _rec("c", 1, _scores(), flags=(flag,)),
        _rec("c", 2, None, failure="judge_api_error"),
        _rec("c", 3, None, failure="judge_api_error"),
    ]
    assert case_critical_flags(recs, "c") == ()


def test_case_failure_types_and_taxonomy():
    records = [
        _rec("c", 1, None, failure="judge_api_error"),
        _rec("c", 2, None, failure="judge_api_error"),
        _rec("d", 1, None, failure="evidence_grounding_error"),
    ]
    assert case_failure_types(records, "c") == ["judge_api_error"]
    assert failure_taxonomy_counts(records) == {
        "judge_api_error": 2,
        "evidence_grounding_error": 1,
    }


def test_global_metrics_mean_median_stdev_over_eligible_cases():
    cases = [_case("c1"), _case("c2"), _case("c3")]
    records = []
    # c1: D1 = 4,4,4 -> 4.0 ; c2: D1 = 2,2,2 -> 2.0 ; c3 excluded (1/3 ok)
    records += [_rec("c1", r, _scores(4)) for r in (1, 2, 3)]
    records += [_rec("c2", r, _scores(2)) for r in (1, 2, 3)]
    records += [_rec("c3", 1, _scores(1)),
                _rec("c3", 2, None, failure="judge_api_error"),
                _rec("c3", 3, None, failure="judge_api_error")]
    metrics = global_metrics(records, cases)

    assert metrics["total_cases"] == 3
    assert metrics["eligible_case_count"] == 2
    assert metrics["excluded_case_count"] == 1
    assert metrics["excluded_case_ids"] == ["c3"]
    assert metrics["expected_calls"] == 9
    assert metrics["successful_calls"] == 7
    assert metrics["failed_calls"] == 2
    assert metrics["operational_success_rate"] == round(7 / 9, 4)

    d1 = metrics["dimensions"]["D1"]
    assert d1["n"] == 2                      # excluded case excluded from stats
    assert d1["mean"] == 3.0                 # (4.0 + 2.0) / 2
    assert d1["median"] == 3.0               # median of [2.0, 4.0]
    # sample (n-1) standard deviation of [4.0, 2.0] = sqrt(2)
    assert d1["stdev"] == 1.4142

    assert metrics["overall_score"]["n"] == 2
    assert metrics["overall_score"]["mean"] == 75.0  # (100 + 50) / 2
    assert metrics["critical_flag_total"] == 0
    assert metrics["failure_taxonomy_counts"] == {"judge_api_error": 2}


def test_critical_flag_counts_over_eligible_cases_only():
    cases = [_case("c1"), _case("c2")]
    flag = "content_anchor_contradiction"
    records = [_rec("c1", r, _scores(), flags=(flag,)) for r in (1, 2, 3)]
    records += [_rec("c2", r, _scores(), flags=(flag,)) for r in (1, 2, 3)]
    counts = critical_flag_counts(records, cases)
    assert counts[flag] == 2
    assert sum(counts.values()) == 2


def test_intent_metrics_cover_six_intents():
    cases = [
        _case("c1", intent="elicitation"),
        _case("c2", intent="elicitation"),
        _case("c3", intent="extension"),
    ]
    records = [_rec("c1", r, _scores(4), intent="elicitation") for r in (1, 2, 3)]
    records += [_rec("c2", r, _scores(2), intent="elicitation") for r in (1, 2, 3)]
    records += [_rec("c3", r, _scores(3), intent="extension") for r in (1, 2, 3)]
    metrics = intent_metrics(records, cases)

    assert set(metrics) == set(INTENTS)
    # total / eligible / excluded are always reported together.
    assert metrics["elicitation"]["n_total"] == 2
    assert metrics["elicitation"]["n_eligible"] == 2
    assert metrics["elicitation"]["n_excluded"] == 0
    assert metrics["elicitation"]["excluded_case_ids"] == []
    assert metrics["elicitation"]["dimensions"]["D1"]["mean"] == 3.0
    assert metrics["elicitation"]["overall"]["mean"] == 75.0
    assert metrics["extension"]["n_eligible"] == 1
    assert metrics["extension"]["overall"]["mean"] == 75.0
    # unused intents report n=0 and null statistics
    assert metrics["scaffolding"]["n_total"] == 0
    assert metrics["scaffolding"]["n_eligible"] == 0
    assert metrics["scaffolding"]["n_excluded"] == 0
    assert metrics["scaffolding"]["overall"]["n"] == 0


def test_intent_metrics_distinguish_total_eligible_and_excluded():
    """An operational exclusion must never look like a smaller population."""
    cases = [
        _case("c1", intent="elicitation"),
        _case("c2", intent="elicitation"),
    ]
    records = [_rec("c1", r, _scores(4), intent="elicitation") for r in (1, 2, 3)]
    # c2 loses two of three repeats -> excluded, but still counted in n_total.
    records += [_rec("c2", 1, _scores(1), intent="elicitation")]
    records += [
        _rec("c2", r, None, failure="judge_api_error", intent="elicitation")
        for r in (2, 3)
    ]
    m = intent_metrics(records, cases)["elicitation"]
    assert m["n_total"] == 2
    assert m["n_eligible"] == 1
    assert m["n_excluded"] == 1
    assert m["excluded_case_ids"] == ["c2"]
    # the excluded case contributes nothing to the statistics
    assert m["dimensions"]["D1"]["n"] == 1
    assert m["overall"]["n"] == 1
    assert m["overall"]["mean"] == 100.0


def test_block_metrics_cover_three_blocks():
    cases = [_case("a1", block="A"), _case("b1", block="B"), _case("c1", block="C")]
    records = [_rec("a1", r, _scores(4), block="A") for r in (1, 2, 3)]
    records += [_rec("b1", r, _scores(2), block="B") for r in (1, 2, 3)]
    records += [_rec("c1", r, _scores(3), block="C") for r in (1, 2, 3)]
    metrics = block_metrics(records, cases)

    assert set(metrics) == {"A", "B", "C"}
    assert metrics["A"]["block_name"] == "controlled_contrast"
    assert metrics["A"]["n_total"] == 1
    assert metrics["A"]["n_eligible"] == 1
    assert metrics["A"]["n_excluded"] == 0
    assert metrics["A"]["excluded_case_ids"] == []
    assert metrics["A"]["overall"]["mean"] == 100.0
    assert metrics["B"]["block_name"] == "cross_domain_generalization"
    assert metrics["B"]["overall"]["mean"] == 50.0
    assert metrics["C"]["block_name"] == "hard_adversarial"
    assert metrics["C"]["overall"]["mean"] == 75.0


def test_block_metrics_distinguish_total_eligible_and_excluded():
    cases = [_case("a1", block="A"), _case("a2", block="A")]
    records = [_rec("a1", r, _scores(4), block="A") for r in (1, 2, 3)]
    # a2: 1/3 successful -> excluded, but still part of the block population.
    records += [_rec("a2", 1, _scores(1), block="A")]
    records += [
        _rec("a2", r, None, failure="judge_api_error", block="A") for r in (2, 3)
    ]
    m = block_metrics(records, cases)["A"]
    assert m["n_total"] == 2
    assert m["n_eligible"] == 1
    assert m["n_excluded"] == 1
    assert m["excluded_case_ids"] == ["a2"]
    assert m["overall"]["n"] == 1
    assert m["overall"]["mean"] == 100.0


def test_case_diagnostics_thresholds():
    cases = [_case("c1")]
    records = [
        _rec("c1", 1, _scores(4, **{D[0]: 2, D[1]: 1})),
        _rec("c1", 2, _scores(4, **{D[0]: 3, D[1]: 2})),
        _rec("c1", 3, _scores(4, **{D[0]: 2, D[1]: 1})),
    ]
    rows = case_diagnostics(records, cases)
    assert len(rows) == 1
    row = rows[0]
    assert row["case_id"] == "c1"
    assert row["successful_repeats"] == 3
    assert row["eligible"] is True
    assert row["exclusion_reason"] is None
    # D1 mean = (2+3+2)/3 = 2.3333 -> weak, not severe
    # D2 mean = (1+2+1)/3 = 1.3333 -> weak AND severe
    assert row["dimension_means"]["D1"] == round(7 / 3, 4)
    assert row["dimension_means"]["D2"] == round(4 / 3, 4)
    assert row["weak_dimensions"] == ["D1", "D2"]
    assert row["severe_dimensions"] == ["D2"]
    assert WEAKNESS_THRESHOLD == 3.0
    assert SEVERE_WEAKNESS_THRESHOLD == 2.0


def test_case_diagnostics_marks_excluded_cases():
    cases = [_case("c1"), _case("c2")]
    records = [_rec("c1", r, _scores()) for r in (1, 2, 3)]
    records += [_rec("c2", 1, _scores())]
    rows = case_diagnostics(records, cases)
    by_id = {row["case_id"]: row for row in rows}
    assert by_id["c1"]["eligible"] is True
    assert by_id["c1"]["exclusion_reason"] is None
    assert by_id["c2"]["eligible"] is False
    assert by_id["c2"]["exclusion_reason"] == "excluded_due_to_operational_failure"
    assert by_id["c2"]["failure_types"] == []


# ---------------------------------------------------------------------------
# 5. End-to-end offline execution (scripted judge; no API).
# ---------------------------------------------------------------------------
def test_end_to_end_offline_all_90_calls_succeed():
    run = prepare_baseline_run()
    judge = ScriptedJudge(_build_responses(run.cases))
    execute_baseline_run(run, judge)

    assert judge.calls == EXPECTED_CALLS == 90
    assert len(run.records) == 90
    assert len(run.raw_evaluations) == 90
    assert all(r.scores is not None for r in run.records)
    assert run.dry_run is False
    assert run.judge_model_reported == (FROZEN_JUDGE_MODEL_REQUESTED,)

    # repeat labels strictly 1/2/3 for every case.
    assert all(r.repeat_index in (1, 2, 3) for r in run.records)
    for case in run.cases:
        repeats = sorted(
            r.repeat_index for r in run.records if r.case_id == case.case_id
        )
        assert repeats == [1, 2, 3]

    agg = aggregate(run)
    g = agg["global"]
    assert g["eligible_case_count"] == 30
    assert g["excluded_case_count"] == 0
    assert g["operational_success_rate"] == 1.0
    assert g["overall_score"]["mean"] == 100.0
    assert set(agg["intent"]) == set(INTENTS)
    assert set(agg["block"]) == {"A", "B", "C"}
    assert len(agg["cases"]) == 30

    # evaluations.jsonl records carry the 1-based repeat label.
    assert {e["repeat_index"] for e in run.raw_evaluations} == {1, 2, 3}
    assert all(
        e["evaluation_id"].endswith(f"__r{e['repeat_index']}")
        for e in run.raw_evaluations
    )


def test_end_to_end_excludes_case_with_two_failures():
    run = prepare_baseline_run()
    victim = run.cases[0].case_id
    judge = ScriptedJudge(
        _build_responses(run.cases, failures={victim: {1, 2}})
    )
    execute_baseline_run(run, judge)

    agg = aggregate(run)
    g = agg["global"]
    assert g["successful_calls"] == 88
    assert g["failed_calls"] == 2
    assert g["eligible_case_count"] == 29
    assert g["excluded_case_count"] == 1
    assert g["excluded_case_ids"] == [victim]
    assert g["failure_taxonomy_counts"] == {"judge_api_error": 2}
    # The excluded case contributes nothing to the semantic statistics.
    assert g["dimensions"]["D1"]["n"] == 29
    assert g["overall_score"]["n"] == 29
    row = next(r for r in agg["cases"] if r["case_id"] == victim)
    assert row["eligible"] is False
    assert row["exclusion_reason"] == "excluded_due_to_operational_failure"
    assert row["successful_repeats"] == 1


def test_end_to_end_exclusion_is_visible_per_intent_and_per_block():
    """An excluded case must stay visible as n_total / n_excluded, not vanish."""
    run = prepare_baseline_run()
    victim = run.cases[0]
    judge = ScriptedJudge(
        _build_responses(run.cases, failures={victim.case_id: {1, 2, 3}})
    )
    execute_baseline_run(run, judge)
    agg = aggregate(run)

    block = agg["block"][victim.block]
    expected_total = sum(1 for c in run.cases if c.block == victim.block)
    assert block["n_total"] == expected_total
    assert block["n_eligible"] == expected_total - 1
    assert block["n_excluded"] == 1
    assert block["excluded_case_ids"] == [victim.case_id]

    intent = agg["intent"][victim.intent]
    expected_intent_total = sum(1 for c in run.cases if c.intent == victim.intent)
    assert intent["n_total"] == expected_intent_total
    assert intent["n_eligible"] == expected_intent_total - 1
    assert intent["n_excluded"] == 1
    assert intent["excluded_case_ids"] == [victim.case_id]


def test_end_to_end_critical_flags_strict_majority():
    run = prepare_baseline_run()
    flag = "material_off_anchor_content"
    flags_by_repeat = {1: (flag,), 2: (flag,), 3: ()}

    def responses(cases):
        out = []
        for case in cases:
            plan_doc = _canonical_plan_doc(case)
            for repeat in (1, 2, 3):
                out.append(
                    _judge_payload(_scores(), plan_doc, flags_by_repeat[repeat])
                )
        return out

    judge = ScriptedJudge(responses(run.cases))
    execute_baseline_run(run, judge)
    agg = aggregate(run)
    assert agg["global"]["critical_flag_counts"][flag] == 30
    assert agg["global"]["critical_flag_total"] == 30


# ---------------------------------------------------------------------------
# 6. Frozen judge condition binding + metadata isolation.
# ---------------------------------------------------------------------------
def test_frozen_judge_config_binding():
    judge = ScriptedJudge(["{}"])
    cfg = build_frozen_judge_config(judge)
    assert cfg.judge_provider == "openrouter"
    assert cfg.judge_model_requested == "qwen/qwen3.5-plus-20260420"
    assert cfg.temperature == 0
    assert cfg.structured_output_enabled is False
    assert cfg.retry_enabled is False
    assert cfg.self_repair_enabled is False
    assert cfg.judge_prompt_version == "v0.1"
    assert len(cfg.judge_prompt_sha256) == 64
    assert FROZEN_RETRY_ENABLED is False
    assert FROZEN_SELF_REPAIR_ENABLED is False
    assert FROZEN_STRUCTURED_OUTPUT_ENABLED is False


def test_frozen_judge_config_rejects_mismatched_backend():
    class WrongModel(ScriptedJudge):
        model = "tencent/hy3"

    class WrongProvider(ScriptedJudge):
        provider = "other"

    class Structured(ScriptedJudge):
        structured_output_enabled = True

    with pytest.raises(ValueError, match="model mismatch"):
        build_frozen_judge_config(WrongModel(["{}"]))
    with pytest.raises(ValueError, match="provider mismatch"):
        build_frozen_judge_config(WrongProvider(["{}"]))
    with pytest.raises(ValueError, match="structured_output"):
        build_frozen_judge_config(Structured(["{}"]))


def test_build_baseline_judge_is_gated_on_a_present_api_key():
    """No key -> no Judge can be constructed (formal mode must fail fast).

    Constructing the client performs no network I/O; the key is only stored.
    """
    assert build_baseline_judge({}) is None
    assert build_baseline_judge({"OPENROUTER_API_KEY": ""}) is None
    assert build_baseline_judge({"OPENROUTER_API_KEY": "   "}) is None

    judge = build_baseline_judge({"OPENROUTER_API_KEY": "offline-placeholder"})
    assert judge is not None
    assert judge.provider == FROZEN_JUDGE_PROVIDER
    assert judge.model == FROZEN_JUDGE_MODEL_REQUESTED
    # Provider/model/base-url are frozen, never taken from the environment.
    assert build_baseline_judge(
        {"OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL": "other/model"}
    ).model == FROZEN_JUDGE_MODEL_REQUESTED


def test_experiment_metadata_never_reaches_the_judge_payload():
    run = prepare_baseline_run()
    case = run.cases[0]
    # One call only: build a single-response judge for this case.
    judge = ScriptedJudge(
        [_judge_payload(_scores(), _canonical_plan_doc(case))]
    )
    cfg = build_frozen_judge_config(judge)
    evaluate_one(case, 1, judge, cfg)

    assert judge.calls == 1
    combined = judge.systems[0] + "\n" + judge.users[0]
    # Experiment metadata MUST NOT leak into the Judge payload.
    # (``case.block`` is a single letter ("A") that occurs in ordinary English
    # prose, so it is not asserted here; block_name is distinctive.)
    assert case.case_id not in combined
    assert case.block_name not in combined
    assert case.source_run_id not in combined
    assert "generator_version" not in combined
    assert "evaluation_id" not in combined
    # Layer-1-visible content SHOULD appear.
    assert case.input_doc["instructional_content"]["content_anchor"] in combined


# ---------------------------------------------------------------------------
# 7. Artifacts.
# ---------------------------------------------------------------------------
def test_write_artifacts_dry_run(tmp_path):
    run = prepare_baseline_run()
    out = tmp_path / "dry"
    write_artifacts(run, out, agg=None)
    assert (out / "run_manifest.json").is_file()
    assert (out / "summary.json").is_file()
    assert (out / "README.md").is_file()
    # No repeat-level results in dry-run.
    assert not (out / "evaluations.jsonl").exists()
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["metrics"] is None
    assert summary["protocol_status"] == "Frozen"
    assert summary["source_population_sha256"] == SOURCE_POPULATION_SHA256
    assert summary["source_population_sha256_match"] is True
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_population_sha256_match"] is True


def test_write_artifacts_full_and_contain_no_secrets(tmp_path):
    run = prepare_baseline_run()
    judge = ScriptedJudge(_build_responses(run.cases))
    execute_baseline_run(run, judge)
    agg = aggregate(run)

    out = tmp_path / "full"
    write_artifacts(run, out, agg=agg)

    for name in (
        "run_manifest.json",
        "summary.json",
        "evaluations.jsonl",
        "case_metrics.csv",
        "intent_metrics.csv",
        "block_metrics.csv",
        "README.md",
    ):
        assert (out / name).is_file(), name

    # evaluations.jsonl: 90 lines, each with the 1-based repeat label.
    lines = [
        json.loads(line)
        for line in (out / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 90
    assert {line["repeat_index"] for line in lines} == {1, 2, 3}

    # CSV headers / row counts.
    with (out / "case_metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert "case_id" in rows[0] and "D6" in rows[0] and "overall_mean" in rows[0]

    with (out / "intent_metrics.csv").open(encoding="utf-8") as handle:
        intent_rows = list(csv.DictReader(handle))
    assert [r["intent"] for r in intent_rows] == list(INTENTS)
    # total / eligible / excluded are all explicit columns.
    assert all(
        {"n_total", "n_eligible", "n_excluded", "excluded_case_ids"} <= set(r)
        for r in intent_rows
    )
    assert sum(int(r["n_eligible"]) for r in intent_rows) == 30

    with (out / "block_metrics.csv").open(encoding="utf-8") as handle:
        block_rows = list(csv.DictReader(handle))
    assert [r["block"] for r in block_rows] == ["A", "B", "C"]
    assert [r["n_total"] for r in block_rows] == ["12", "12", "6"]
    assert [r["n_eligible"] for r in block_rows] == ["12", "12", "6"]
    assert [r["n_excluded"] for r in block_rows] == ["0", "0", "0"]

    # No secret material in any artifact.
    blob = "".join(
        p.read_text(encoding="utf-8")
        for p in out.iterdir()
        if p.suffix in (".json", ".csv", ".md", ".jsonl")
    )
    assert "OPENROUTER_API_KEY" not in blob
    assert "api_key" not in blob


def test_summary_is_descriptive_and_has_no_verdict():
    run = prepare_baseline_run()
    judge = ScriptedJudge(_build_responses(run.cases))
    execute_baseline_run(run, judge)
    summary = build_summary(run, aggregate(run))

    assert json.dumps(summary, ensure_ascii=False)
    assert summary["protocol_version"] == PROTOCOL_VERSION == "v0.1"
    assert summary["protocol_status"] == PROTOCOL_STATUS == "Frozen"
    assert summary["source_population_sha256"] == SOURCE_POPULATION_SHA256
    assert summary["source_population_sha256_match"] is True
    assert summary["generator_version_provenance"] == GENERATOR_VERSION_PROVENANCE
    # No Generator PASS/FAIL verdict is emitted.
    assert summary["verdict"] is None
    assert "PASS/FAIL threshold" in summary["verdict_note"]
    # Required global-metric blocks.
    g = summary["global_metrics"]
    for key in (
        "eligible_case_count",
        "total_cases",
        "excluded_case_count",
        "operational_success_rate",
        "dimensions",
        "overall_score",
        "critical_flag_counts",
        "failure_taxonomy_counts",
    ):
        assert key in g, key
    assert set(summary["intent_metrics"]) == set(INTENTS)
    assert set(summary["block_metrics"]) == {"A", "B", "C"}
    assert len(summary["case_diagnostics"]) == 30
    assert summary["diagnostic_thresholds"]["weakness_dimension_mean_lt"] == 3.0
    assert summary["diagnostic_thresholds"]["severe_weakness_dimension_mean_lt"] == 2.0
