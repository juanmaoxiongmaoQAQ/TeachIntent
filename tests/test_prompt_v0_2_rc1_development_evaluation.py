"""Offline tests for the Prompt v0.2-rc.1 **paired development evaluation**.

Compares two FINISHED sides over the SAME frozen 30-case Pilot population:

    v0.1 side    Generator v0.1 + Prompt v0.1       (baseline run, read-only)
    rc.1 side    Generator v0.1 + Prompt v0.2-rc.1  (candidate run, read-only)

Every execution test uses a scripted offline Judge with precomputed,
evidence-grounded (or deliberately invalid) responses, so no OpenRouter call is
ever made. Backoff is injected as a recording sleeper — tests never wait.

Coverage mirrors Section 14 of the development comparison request:

 1. both sides' case IDs exact match
 2. candidate 30/30 usable (A/B/C = 12/12/6, all success, all rc.1)
 3. frozen baseline evaluation loads correctly
 4. baseline is NOT regenerated
 5. baseline is NOT re-Judge-evaluated
 6. candidate planned semantic repeats = 90
 7. max physical attempts = 3
 8. retry taxonomy identical to Protocol v0.2
 9. plan eligibility is >= 2/3 successful semantic repeats
10. pair eligibility rule
11. delta calculation
12. a failed semantic repeat is never scored as 0
13. dry-run makes no API call
14. artifact structure + provenance
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from teachintent.evaluator import JudgeCompletion
from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.generator_evaluation import baseline_v0_1 as v1
from teachintent.generator_evaluation import baseline_v0_2 as v2
from teachintent.prompt_development import development_evaluation as de

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "run_prompt_v0_2_rc1_development_evaluation.py"

D = DIMENSION_IDS


# ---------------------------------------------------------------------------
# Offline Judge + helpers.
# ---------------------------------------------------------------------------
class ScriptedJudge:
    """Deterministic offline Judge: one precomputed response per call, in order.

    A response may be an ``Exception`` instance, which is raised instead
    (simulating operational failures with zero network access).
    """

    provider = v2.FROZEN_JUDGE_PROVIDER
    model = v2.FROZEN_JUDGE_MODEL_REQUESTED
    structured_output_enabled = False

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system, user, *, temperature=0.0):
        index = self.calls
        self.calls += 1
        if index >= len(self._responses):
            raise AssertionError(
                f"ScriptedJudge exhausted after {len(self._responses)} responses"
            )
        response = self._responses[index]
        if isinstance(response, BaseException):
            raise response
        return JudgeCompletion(
            content=response,
            reported_model=self.model,
            structured_object=None,
            finish_reason="stop",
        )


class RecordingSleeper:
    """Injectable backoff: records every requested delay, never actually sleeps."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _scores(value: int = 4, **overrides: int) -> dict[str, int]:
    base = {d: value for d in D}
    # Overrides may use the short labels ("D5") or the long dimension ids; map
    # the short labels onto the ids the score dict is actually keyed by.
    for key, val in overrides.items():
        base[v1._LABEL_TO_DIM.get(key, key)] = val
    return base


def _grounded_text(plan_doc: dict) -> str:
    """A 40-char prefix of the plan's canonical JSON — always grounded."""
    return json.dumps(
        plan_doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )[:40]


def _valid_payload(plan_doc: dict, scores: dict[str, int] | None = None) -> str:
    evidence_text = _grounded_text(plan_doc)
    return json.dumps(
        {
            "scores": {
                d: {
                    "score": (scores or _scores())[d],
                    "evidence": [{"source": "plan", "text": evidence_text}],
                    "brief_justification": "ok",
                }
                for d in D
            },
            "critical_flags": [],
        },
        ensure_ascii=False,
    )


def _parse_error_payload() -> str:
    return "I am afraid I cannot do that; here is prose instead of JSON."


def _flat_responses(
    cases,
    *,
    spec: dict | None = None,
    scores: dict[str, int] | None = None,
) -> list:
    """Flat response queue consumed in execution order (case, repeat, attempt).

    ``spec`` maps ``(case_id, repeat_index)`` to a list of per-attempt
    responses. Missing entries default to a single valid payload.
    """
    spec = spec or {}
    out: list = []
    for case in cases:
        plan_doc = json.loads(case.raw_response)
        for repeat in (1, 2, 3):
            seq = spec.get((case.case_id, repeat))
            if seq is None:
                out.append(_valid_payload(plan_doc, scores))
            else:
                out.extend(seq)
    return out


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def prepared():
    """One offline pre-flight shared by the read-only tests."""
    return de.prepare_development_evaluation()


@pytest.fixture()
def executed(prepared):
    """A fully executed candidate side with a uniform, scripted offline Judge."""
    run = de.prepare_development_evaluation()
    judge = ScriptedJudge(_flat_responses(run.candidate_run.cases))
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())
    return run, judge


# ---------------------------------------------------------------------------
# 1-2. Population identity and candidate usability.
# ---------------------------------------------------------------------------
def test_case_ids_exact_match(prepared) -> None:
    integrity = prepared.integrity
    baseline_ids = set(prepared.baseline.case_ids)
    assert set(integrity.case_ids) == baseline_ids
    assert integrity.case_ids_exact_match is True
    assert integrity.unique_case_ids is True
    assert integrity.duplicate_case_ids == []
    # 30 on both sides, no duplicates anywhere.
    assert len(integrity.case_ids) == 30
    assert len(baseline_ids) == 30


def test_candidate_30_cases_all_usable(prepared) -> None:
    integrity = prepared.integrity
    assert integrity.total_cases == 30
    assert integrity.restorable_cases == 30
    assert integrity.ok is True
    assert integrity.messages == []
    # A/B/C = 12/12/6, inherited from the frozen population.
    assert integrity.per_block_counts == {"A": 12, "B": 12, "C": 6}
    # Every case is the candidate prompt and a successful generation.
    assert integrity.prompt_versions == [de.CANDIDATE_PROMPT_VERSION]
    assert integrity.generation_outcomes == ["success"]


def test_candidate_inputs_are_byte_identical_to_v0_1(prepared) -> None:
    assert prepared.integrity.input_fingerprints_match is True
    baseline_sha = prepared.baseline.input_sha256_by_case
    for case_id, sha in prepared.integrity.input_sha256_by_case.items():
        assert baseline_sha[case_id] == sha


# ---------------------------------------------------------------------------
# 3. Frozen baseline evaluation loads correctly.
# ---------------------------------------------------------------------------
def test_baseline_evaluation_loads_the_frozen_run(prepared) -> None:
    baseline = prepared.baseline
    assert baseline.run_id == de.BASELINE_EVALUATION_RUN_ID
    assert baseline.manifest["protocol_version"] == v2.PROTOCOL_VERSION
    assert baseline.manifest["protocol_status"] == "Frozen"
    # The baseline side is Prompt v0.1, not the candidate.
    assert baseline.manifest["prompt_version"] == de.BASELINE_PROMPT_VERSION
    assert len(baseline.case_rows) == 30
    # The frozen run really carries evaluations (it is not a dry-run).
    assert baseline.manifest.get("dry_run") is False


def test_baseline_load_rejects_a_wrong_or_missing_run(tmp_path) -> None:
    with pytest.raises(de.DevelopmentEvaluationError):
        de.load_baseline_evaluation(tmp_path / "nope")
    with pytest.raises(de.DevelopmentEvaluationError):
        de.load_baseline_evaluation(tmp_path)


# ---------------------------------------------------------------------------
# 4-5. The v0.1 side is never regenerated and never re-evaluated.
# ---------------------------------------------------------------------------
def test_baseline_is_not_reevaluated(executed, monkeypatch) -> None:
    """Every physical attempt must target a v0.2-rc.1 case — never a v0.1 one."""
    run, judge = executed

    seen: list[str] = []
    original = v2.evaluate_attempt

    def spy(case, repeat_index, attempt_index, judge_, judge_config):
        seen.append(case.prompt_version)
        return original(case, repeat_index, attempt_index, judge_, judge_config)

    monkeypatch.setattr(v2, "evaluate_attempt", spy)
    run2 = de.prepare_development_evaluation()
    judge2 = ScriptedJudge(_flat_responses(run2.candidate_run.cases))
    de.execute_candidate_evaluation(run2, judge2, sleep_fn=RecordingSleeper())

    assert seen, "no attempt was executed"
    # Not one v0.1 plan reached the Evaluator.
    assert set(seen) == {de.CANDIDATE_PROMPT_VERSION}
    # 90 semantic repeats, first-attempt success each -> exactly 90 calls.
    # Re-evaluating the baseline too would be 180.
    assert len(seen) == 90
    assert judge2.calls == 90


def test_manifest_declares_no_baseline_rerun(executed) -> None:
    run, _ = executed
    manifest = de.build_development_manifest(run)
    assert manifest["v0_1_generation_rerun"] is False
    assert manifest["v0_1_evaluation_rerun"] is False
    assert manifest["baseline_evaluation_run"] == de.BASELINE_EVALUATION_RUN_ID
    assert manifest["candidate_generation_run"] == de.CANDIDATE_GENERATION_RUN_ID


# ---------------------------------------------------------------------------
# 6-8. Frozen acquisition policy.
# ---------------------------------------------------------------------------
def test_candidate_planned_semantic_repeats_is_90(prepared) -> None:
    cand = prepared.candidate_run
    assert cand.planned_semantic_repeats == 90
    assert cand.semantic_repeats_per_case == 3
    assert len(cand.cases) == 30


def test_max_physical_attempts_is_3(prepared) -> None:
    cand = prepared.candidate_run
    assert cand.max_attempts_per_semantic_repeat == 3
    assert cand.max_possible_physical_attempts == 270


def test_retry_taxonomy_is_identical_to_protocol_v0_2(prepared, monkeypatch) -> None:
    """The candidate run reuses the frozen taxonomy object, by identity."""
    manifest = de.build_development_manifest(prepared)
    assert manifest["retryable_failure_types"] == list(v2.RETRYABLE_FAILURE_TYPES)
    assert manifest["non_retryable_failure_types"] == list(
        v2.NON_RETRYABLE_FAILURE_TYPES
    )
    assert manifest["evaluator_retry_enabled"] is v2.EVALUATOR_RETRY_ENABLED
    assert manifest["attempt_retry_enabled"] is v2.BASELINE_ATTEMPT_RETRY_ENABLED
    assert manifest["max_attempts_per_semantic_repeat"] == (
        v2.MAX_ATTEMPTS_PER_SEMANTIC_REPEAT
    )
    assert manifest["retry_backoff_policy"] == {
        key: list(value) for key, value in v2.RETRY_BACKOFF_SECONDS.items()
    }
    # The policy is imported, never redesigned — the frozen module is the one
    # and only source of truth.
    assert de.RETRYABLE_FAILURE_TYPES is v2.RETRYABLE_FAILURE_TYPES
    assert de.NON_RETRYABLE_FAILURE_TYPES is v2.NON_RETRYABLE_FAILURE_TYPES


def test_execution_rejects_a_redesigned_attempt_policy(prepared) -> None:
    judge = ScriptedJudge([])
    with pytest.raises(ValueError, match="Protocol v0.2 Section 7"):
        de.execute_candidate_evaluation(prepared, judge, max_attempts=5)


# ---------------------------------------------------------------------------
# 9-10. Eligibility.
# ---------------------------------------------------------------------------
def test_plan_eligibility_is_at_least_2_of_3(executed) -> None:
    run, _ = executed
    assert v1.MIN_SUCCESSFUL_REPEATS == 2
    assert run.candidate_run.semantic_repeats_per_case == 3
    # With a healthy Judge every case clears 3/3, hence also >= 2/3.
    for case in run.candidate_run.cases:
        assert v1.case_eligible(run.candidate_run.records, case.case_id) is True


def test_pair_eligibility_both_sides_healthy(executed) -> None:
    run, _ = executed
    rows = de.case_pair_rows(run)
    assert len(rows) == 30
    # The frozen v0.1 baseline has 4 operationally-ineligible cases; the rc.1
    # side is healthy for all 30. Pair eligibility is the intersection: 26.
    # rc.1 success never triggers a v0.1 rerun, so those 4 stay excluded.
    eligible = [r for r in rows if r["pair_eligible"]]
    excluded = [r for r in rows if not r["pair_eligible"]]
    assert len(eligible) == 26
    assert len(excluded) == 4
    assert all(r["exclusion_reason"] == "v0_1_side_ineligible" for r in excluded)
    assert sorted(r["case_id"] for r in excluded) == [
        "PILOT-A-EXP-02",
        "PILOT-B-EXT-02",
        "PILOT-B-SCA-02",
        "PILOT-C-COR-01",
    ]
    comparison = de.build_paired_comparison(run, rows)
    coverage = comparison["coverage"]
    assert coverage["total_cases"] == 30
    assert coverage["v0_1_eligible"] == 26
    assert coverage["rc_1_eligible"] == 30
    assert coverage["pair_eligible"] == 26
    assert coverage["excluded_case_ids"] == sorted(
        r["case_id"] for r in excluded
    )
    assert all(
        e["exclusion_reason"] == "v0_1_side_ineligible"
        for e in coverage["exclusions"]
    )
    assert coverage["v0_1_side_rerun"] is False


def test_pair_eligibility_excludes_a_rc_1_failure() -> None:
    """An rc.1 side with < 2 successful repeats is excluded, v0.1 is NOT rerun."""
    run = de.prepare_development_evaluation()
    victim = run.candidate_run.cases[0].case_id
    plan_doc = json.loads(run.candidate_run.cases[0].raw_response)
    spec = {
        (victim, 1): [_parse_error_payload()] * 3,
        (victim, 2): [_parse_error_payload()] * 3,
        (victim, 3): [_valid_payload(plan_doc)],
    }
    judge = ScriptedJudge(_flat_responses(run.candidate_run.cases, spec=spec))
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())

    rows = de.case_pair_rows(run)
    victim_row = next(r for r in rows if r["case_id"] == victim)
    # 1/3 successful -> ineligible on the rc.1 side.
    assert victim_row["rc_1_eligible"] is False
    assert victim_row["v0_1_eligible"] is True
    assert victim_row["pair_eligible"] is False
    assert victim_row["exclusion_reason"] == "rc_1_side_ineligible"
    # The failed side's delta is undefined — not a fabricated 0.
    assert victim_row["delta_D5"] is None

    coverage = de.build_paired_comparison(run, rows)["coverage"]
    # 26 baseline-eligible cases minus the 1 rc.1 victim = 25 pairs.
    assert coverage["pair_eligible"] == 25
    # Excluded = the 4 frozen baseline-ineligible cases + the rc.1 victim.
    assert len(coverage["excluded_case_ids"]) == 5
    assert victim in coverage["excluded_case_ids"]
    victim_exclusion = next(
        e for e in coverage["exclusions"] if e["case_id"] == victim
    )
    assert victim_exclusion["exclusion_reason"] == "rc_1_side_ineligible"
    # The four frozen baseline exclusions are untouched and never rerun.
    baseline_excluded = [
        e
        for e in coverage["exclusions"]
        if e["exclusion_reason"] == "v0_1_side_ineligible"
    ]
    assert len(baseline_excluded) == 4


# ---------------------------------------------------------------------------
# 11. Delta calculation.
# ---------------------------------------------------------------------------
def test_delta_is_rc1_minus_v0_1() -> None:
    run = de.prepare_development_evaluation()
    # A uniform, known score set on the candidate side. D5 is lowered to 2 (a
    # valid rubric score, clearly different from the default 4) so the delta is
    # non-trivially negative rather than a constant 0.
    rc1_scores = _scores(4, D5=2)
    judge = ScriptedJudge(
        _flat_responses(run.candidate_run.cases, scores=rc1_scores)
    )
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())

    rows = de.case_pair_rows(run)
    # The candidate side is uniformly D5 = 2 for every one of the 30 cases,
    # regardless of the other side's eligibility.
    assert all(row["rc_1_D5"] == pytest.approx(2.0) for row in rows)

    paired = [r for r in rows if r["pair_eligible"]]
    assert len(paired) == 26  # the 4 baseline-ineligible cases form no pair
    for row in paired:
        v01_d5 = run.baseline.case_rows[row["case_id"]]["dimension_means"]["D5"]
        assert row["delta_D5"] == pytest.approx(round(2.0 - v01_d5, 4))
    # The excluded cases carry no fabricated delta.
    assert all(r["delta_D5"] is None for r in rows if not r["pair_eligible"])

    stats = de.dimension_paired_stats(rows, "D5")
    assert stats["dimension"] == "D5"
    assert stats["n"] == 26
    assert stats["rc_1_mean"] == pytest.approx(2.0)
    assert stats["mean"] == pytest.approx(
        round(sum(r["delta_D5"] for r in paired) / 26, 4), abs=1e-3
    )
    # CI brackets the mean and improved/tied/worsened partition the 26 pairs.
    assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"]
    assert stats["improved"] + stats["tied"] + stats["worsened"] == 26


def test_delta_stats_are_empty_safe() -> None:
    stats = de.delta_stats([])
    assert stats["n"] == 0
    assert stats["mean"] is None
    assert stats["ci95_low"] is None
    assert stats["improved"] == 0


def test_group_breakdown_covers_intent_and_block(executed) -> None:
    run, _ = executed
    rows = de.case_pair_rows(run)
    comparison = de.build_paired_comparison(run, rows)
    breakdown = comparison["breakdown"]
    # Six intents and three blocks.
    assert set(breakdown["by_block"]) == {"A", "B", "C"}
    assert sum(g["n_total"] for g in breakdown["by_block"].values()) == 30
    assert sum(g["n_total"] for g in breakdown["by_intent"].values()) == 30
    block_c = breakdown["by_block"]["C"]
    assert block_c["n_total"] == 6
    assert "D5" in block_c
    assert "paired_delta" in block_c["D5"]


# ---------------------------------------------------------------------------
# 12. A failed semantic repeat is never scored as 0.
# ---------------------------------------------------------------------------
def test_failed_semantic_repeat_is_not_scored_zero() -> None:
    run = de.prepare_development_evaluation()
    victim = run.candidate_run.cases[0].case_id
    plan_doc = json.loads(run.candidate_run.cases[0].raw_response)
    # repeat 3 fails all three attempts; repeats 1-2 succeed with D5 = 2.
    spec = {(victim, 3): [_parse_error_payload()] * 3}
    scores = _scores(4, D5=2)
    judge = ScriptedJudge(
        _flat_responses(run.candidate_run.cases, spec=spec, scores=scores)
    )
    sleeper = RecordingSleeper()
    de.execute_candidate_evaluation(run, judge, sleep_fn=sleeper)

    rows = de.case_pair_rows(run)
    row = next(r for r in rows if r["case_id"] == victim)

    # 2/3 successful -> still eligible.
    assert row["rc_1_successful_repeats"] == 2
    assert row["rc_1_eligible"] is True
    # The mean is over the TWO successful repeats: 2.0.
    # Zero-filling the failed repeat would give (2+2+0)/3 = 1.3333.
    assert row["rc_1_D5"] == pytest.approx(2.0)
    assert row["rc_1_D5"] != pytest.approx(2.0 * 2 / 3)

    # All three failed attempts are preserved in the artifact.
    repeats = [
        r for r in run.candidate_run.repeat_results if r.case_id == victim
    ]
    victim_repeat_3 = next(r for r in repeats if r.repeat_index == 3)
    assert victim_repeat_3.semantic_repeat_success is False
    assert victim_repeat_3.attempt_count == 3
    assert len(victim_repeat_3.attempts) == 3
    # Backoff was applied twice between the three attempts (never a 4th).
    assert len(sleeper.delays) == 2

    # The failed repeat contributes no score, and no zero, anywhere.
    successful = [r for r in repeats if r.semantic_repeat_success]
    assert len(successful) == 2
    assert all(r.final_result is not None for r in successful)


# ---------------------------------------------------------------------------
# 13. dry-run makes no API call.
# ---------------------------------------------------------------------------
def test_cli_dry_run_makes_no_api_call() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "baseline population = 30" in out
    assert "candidate population = 30" in out
    assert "case IDs exact match = True" in out
    assert "planned candidate semantic evaluations = 90" in out
    assert "maximum candidate physical Judge calls = 270" in out
    assert "No API call was made." in out


def test_cli_requires_a_mode() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    # argparse fails fast: never defaults to a real API run.
    assert proc.returncode == 2
    assert "--dry-run" in (proc.stderr + proc.stdout)


def test_dry_run_never_constructs_a_judge(monkeypatch) -> None:
    """The offline pre-flight path must not touch the Judge builder at all."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("dev_eval_cli", CLI)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def explode():
        raise AssertionError("dry-run must never build a Judge")

    monkeypatch.setattr(module, "build_baseline_judge", explode)
    assert module.main(["--dry-run"]) == 0


# ---------------------------------------------------------------------------
# 14. Artifacts.
# ---------------------------------------------------------------------------
def test_artifacts_are_written_with_full_provenance(executed, tmp_path) -> None:
    run, _ = executed
    out = tmp_path / "run"
    de.write_development_artifacts(run, out)

    for name in (
        "run_manifest.json",
        "summary.json",
        "evaluations.jsonl",
        "case_metrics.csv",
        "intent_metrics.csv",
        "block_metrics.csv",
        "paired_comparison.csv",
    ):
        assert (out / name).is_file(), f"missing artifact: {name}"

    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_generation_run"] == "20260831-052126"
    assert manifest["baseline_evaluation_run"] == "20260830T095934Z"
    assert manifest["case_ids_exact_match"] is True
    assert manifest["planned_candidate_semantic_evaluations"] == 90
    assert manifest["maximum_candidate_physical_judge_calls"] == 270
    # Full Judge provenance.
    assert manifest["evaluator_version"] == "v0.1"
    assert manifest["judge_provider"] == "openrouter"
    assert manifest["judge_model_requested"] == "qwen/qwen3.5-plus-20260420"
    assert manifest["temperature"] == 0
    assert manifest["structured_output_enabled"] is False
    assert manifest["self_repair_enabled"] is False
    assert manifest["evaluator_retry_enabled"] is False
    # Both sides identified.
    assert manifest["sides"]["v0_1"]["prompt_version"] == "v0.1"
    assert manifest["sides"]["v0_2_rc_1"]["prompt_version"] == "v0.2-rc.1"

    # evaluations.jsonl: one record per semantic repeat, attempts embedded.
    lines = (out / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 90
    first = json.loads(lines[0])
    assert "attempts" in first
    assert first["attempts"], "every physical attempt must be preserved"

    # paired_comparison.csv: header + 30 rows, deltas present.
    with (out / "paired_comparison.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert "delta_D5" in rows[0]
    assert "delta_D4" in rows[0]
    # 26 pair-eligible cases carry a delta; the 4 frozen baseline-ineligible
    # cases carry an empty delta (never a fabricated 0).
    assert sum(1 for r in rows if r["delta_D5"] != "") == 26
    assert sum(1 for r in rows if r["delta_D5"] == "") == 4

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    # Development evidence: no mechanical verdict.
    assert summary["verdict"] is None
    comparison = summary["paired_comparison"]
    assert comparison["primary"]["dimension"] == "D5"
    assert comparison["primary"]["threshold"] is None
    assert comparison["secondary"]["dimension"] == "D4"
    assert set(comparison["protected"]) == {"D1", "D2", "D3", "D6"}
    assert comparison["interpretation"]["is_confirmatory"] is False


def test_artifacts_are_absent_in_dry_run(tmp_path) -> None:
    """A dry-run writes only the manifest/summary, never evaluation artifacts."""
    run = de.prepare_development_evaluation()
    out = tmp_path / "dry"
    de.write_development_artifacts(run, out)
    assert (out / "run_manifest.json").is_file()
    assert (out / "summary.json").is_file()
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["candidate_side_metrics"] is None
    assert not (out / "evaluations.jsonl").exists()
    assert not (out / "paired_comparison.csv").exists()


# ---------------------------------------------------------------------------
# Source artifacts are never modified.
# ---------------------------------------------------------------------------
def test_frozen_inputs_are_never_written(executed) -> None:
    """The two source runs are read-only: only the candidate run dir may grow."""
    baseline_root = Path(de.BASELINE_EVALUATION_ROOT)
    candidate_root = Path(de.CANDIDATE_GENERATION_ROOT)
    assert baseline_root.is_dir()
    assert candidate_root.is_dir()
    assert de.RESULTS_ROOT != baseline_root
    assert de.RESULTS_ROOT != candidate_root
    # The paired evaluation writes under its own root, never into the others.
    assert de.RESULTS_ROOT.name == "prompt_v0_2_rc1_development_evaluation"
    assert de.RESULTS_ROOT.parent == baseline_root.parents[1]
