"""Offline tests for the **Prompt v0.2-rc.2 paired development evaluation**.

rc.2 is evaluated through the SAME framework as rc.1 — only the loaded
generation run (``20260831-153546``) and the artifact key label (``rc_2``)
differ. These tests pin that down, and pin down that the rc.1 path is still
reproducible afterwards.

Every execution test uses a scripted offline Judge with precomputed responses,
so no OpenRouter call is ever made. Backoff is injected as a recording sleeper —
tests never wait.

Coverage (mirrors the rc.2 evaluation request, Section 10):

 1. the rc.2 generation run loads correctly
 2. 30 cases, exact case-ID match with the v0.1 population
 3. input fingerprints byte-identical to the v0.1 population
 4. the rc.1 evaluation path is still available
 5. rc.2 candidate prompt / version provenance is correct
 6. the v0.1 side is NOT regenerated
 7. the v0.1 side is NOT re-Judge-evaluated
 8. 90 planned candidate semantic evaluations
 9. max physical attempts = 3
10. eligibility logic is unchanged
11. a failed semantic repeat is never scored as 0
12. dry-run makes no API call
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

RC2_GENERATION_RUN_ID = "20260831-153546"
BASELINE_EVALUATION_RUN_ID = "20260830T095934Z"

#: The four frozen baseline cases that are operationally ineligible on the
#: v0.1 side. They can never form a pair and are never rerun to create one.
FROZEN_BASELINE_INELIGIBLE = [
    "PILOT-A-EXP-02",
    "PILOT-B-EXT-02",
    "PILOT-B-SCA-02",
    "PILOT-C-COR-01",
]

#: The rc.2 generation run's measured delivery behaviour (QC'd by hand).
RC2_EMPTY = 27
RC2_NON_EMPTY = 3
RC2_NON_EMPTY_IDS = ["PILOT-A-COR-01", "PILOT-C-COR-01", "PILOT-C-SCA-01"]


# ---------------------------------------------------------------------------
# Offline Judge + helpers (identical in spirit to the rc.1 test module; kept
# local so the two modules stay independently readable).
# ---------------------------------------------------------------------------
class ScriptedJudge:
    """Deterministic offline Judge: one precomputed response per call, in order."""

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
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _scores(value: int = 4, **overrides: int) -> dict[str, int]:
    base = {d: value for d in D}
    for key, val in overrides.items():
        base[v1._LABEL_TO_DIM.get(key, key)] = val
    return base


def _valid_payload(plan_doc: dict, scores: dict[str, int] | None = None) -> str:
    evidence_text = json.dumps(
        plan_doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )[:40]
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


def _flat_responses(cases, *, spec: dict | None = None, scores=None) -> list:
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
def prepared_rc2():
    """One offline rc.2 pre-flight shared by the read-only tests."""
    return de.prepare_development_evaluation(prompt_version="v0.2-rc.2")


@pytest.fixture()
def executed_rc2():
    """A fully executed rc.2 candidate side with a uniform offline Judge."""
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
    judge = ScriptedJudge(_flat_responses(run.candidate_run.cases))
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())
    return run, judge


# ---------------------------------------------------------------------------
# 1-3. rc.2 generation run loads; 30 cases; byte-identical inputs.
# ---------------------------------------------------------------------------
def test_rc2_generation_run_loads(prepared_rc2) -> None:
    run = prepared_rc2
    assert run.candidate_generation_run_id == RC2_GENERATION_RUN_ID
    assert run.candidate_prompt_version == de.PROMPT_VERSION_RC2
    assert run.candidate_label == "rc_2"
    # The run really is the finished rc.2 generation run, read from disk.
    assert run.candidate_run.source_runs[0]["run_id"] == RC2_GENERATION_RUN_ID
    assert run.candidate_run.source_runs[0]["block_name"] == (
        "prompt_v0_2_rc2_development"
    )
    assert Path(run.candidate_run.source_runs[0]["path"]).is_dir()


def test_rc2_30_cases_exact_match(prepared_rc2) -> None:
    integrity = prepared_rc2.integrity
    assert integrity.total_cases == 30
    assert integrity.restorable_cases == 30
    assert integrity.ok is True
    assert integrity.messages == []
    assert integrity.per_block_counts == {"A": 12, "B": 12, "C": 6}
    assert set(integrity.case_ids) == set(prepared_rc2.baseline.case_ids)
    assert integrity.case_ids_exact_match is True
    assert integrity.unique_case_ids is True


def test_rc2_input_fingerprints_match(prepared_rc2) -> None:
    assert prepared_rc2.integrity.input_fingerprints_match is True
    baseline_sha = prepared_rc2.baseline.input_sha256_by_case
    assert len(prepared_rc2.integrity.input_sha256_by_case) == 30
    for case_id, sha in prepared_rc2.integrity.input_sha256_by_case.items():
        assert baseline_sha[case_id] == sha


# ---------------------------------------------------------------------------
# 4. The rc.1 evaluation path is still available and unchanged.
# ---------------------------------------------------------------------------
def test_rc1_evaluation_path_still_available() -> None:
    run = de.prepare_development_evaluation()  # no argument -> rc.1 default
    assert run.candidate_prompt_version == de.CANDIDATE_PROMPT_VERSION
    assert run.candidate_label == "rc_1"
    assert run.candidate_generation_run_id == "20260831-052126"
    assert run.integrity.total_cases == 30
    assert run.integrity.case_ids_exact_match is True
    assert run.integrity.input_fingerprints_match is True
    # rc.1 is still the DEFAULT side: no argument means rc.1.
    assert de.CANDIDATE_PROMPT_VERSION == "v0.2-rc.1"
    assert de.PROMPT_VERSION_RC2 == "v0.2-rc.2"
    assert set(de.SUPPORTED_PROMPT_VERSIONS) == {"v0.2-rc.1", "v0.2-rc.2"}


def test_rc1_and_rc2_use_the_same_frozen_protocol() -> None:
    rc1 = de.prepare_development_evaluation(prompt_version="v0.2-rc.1")
    rc2 = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
    for run in (rc1, rc2):
        cand = run.candidate_run
        assert cand.protocol_version == v2.PROTOCOL_VERSION
        assert cand.protocol_status == "Frozen"
        assert cand.semantic_repeats_per_case == 3
        assert cand.planned_semantic_repeats == 90
        assert cand.max_attempts_per_semantic_repeat == 3
        assert cand.max_possible_physical_attempts == 270
    # Both sides share the same population identity and the same frozen v0.1
    # baseline evaluation — only the candidate artifacts differ.
    assert rc1.baseline.run_id == rc2.baseline.run_id == BASELINE_EVALUATION_RUN_ID
    assert set(rc1.integrity.case_ids) == set(rc2.integrity.case_ids)


def test_results_roots_are_separate() -> None:
    assert de.evaluation_results_root_for_prompt_version("v0.2-rc.1").name == (
        "prompt_v0_2_rc1_development_evaluation"
    )
    assert de.evaluation_results_root_for_prompt_version("v0.2-rc.2").name == (
        "prompt_v0_2_rc2_development_evaluation"
    )
    assert de.candidate_generation_root_for_prompt_version("v0.2-rc.2").parent != (
        de.candidate_generation_root_for_prompt_version("v0.2-rc.1").parent
    )
    with pytest.raises(de.DevelopmentEvaluationError):
        de.evaluation_results_root_for_prompt_version("v0.2-rc.3")
    with pytest.raises(de.DevelopmentEvaluationError):
        de.load_candidate_cases(
            de.load_baseline_evaluation(), prompt_version="v0.2-rc.3"
        )


def test_unsupported_prompt_version_is_rejected() -> None:
    with pytest.raises(de.DevelopmentEvaluationError):
        de.prepare_development_evaluation(prompt_version="v0.2-rc.3")


# ---------------------------------------------------------------------------
# 5. rc.2 candidate prompt / version provenance.
# ---------------------------------------------------------------------------
def test_rc2_provenance_is_recorded(prepared_rc2) -> None:
    run = prepared_rc2
    assert run.integrity.prompt_versions == ["v0.2-rc.2"]
    assert run.integrity.generation_outcomes == ["success"]
    assert run.candidate_run.prompt_version == "v0.2-rc.2"
    assert "v0.2-rc.2" in run.candidate_run.prompt_version_provenance
    # Every restored case carries the rc.2 prompt, never a silent fallback.
    assert {c.prompt_version for c in run.candidate_run.cases} == {"v0.2-rc.2"}

    manifest = de.build_development_manifest(run)
    assert manifest["candidate_prompt_version"] == "v0.2-rc.2"
    assert manifest["candidate_generation_run"] == RC2_GENERATION_RUN_ID
    assert manifest["baseline_evaluation_run"] == BASELINE_EVALUATION_RUN_ID
    assert manifest["sides"]["v0_2_rc_2"]["prompt_version"] == "v0.2-rc.2"
    assert manifest["sides"]["v0_1"]["prompt_version"] == "v0.1"
    # The frozen Judge condition is identical to the rc.1 side.
    assert manifest["evaluator_version"] == "v0.1"
    assert manifest["judge_provider"] == "openrouter"
    assert manifest["judge_model_requested"] == "qwen/qwen3.5-plus-20260420"
    assert manifest["temperature"] == 0
    assert manifest["structured_output_enabled"] is False
    assert manifest["self_repair_enabled"] is False
    assert manifest["evaluator_retry_enabled"] is False


def test_rc2_rejects_a_run_of_the_wrong_prompt(prepared_rc2, tmp_path) -> None:
    """Pointing rc.2 at the rc.1 run must fail the pre-flight, not silently pass."""
    baseline = prepared_rc2.baseline
    rc1_root = de.candidate_generation_root_for_prompt_version("v0.2-rc.1")
    cases, integrity = de.load_candidate_cases(
        baseline, rc1_root, "v0.2-rc.2"
    )
    assert integrity.ok is False
    joined = " ".join(integrity.messages)
    assert "prompt_version" in joined
    with pytest.raises(de.DevelopmentEvaluationError):
        de.prepare_development_evaluation(
            candidate_root=rc1_root, prompt_version="v0.2-rc.2"
        )


# ---------------------------------------------------------------------------
# 6-7. The v0.1 side is never regenerated and never re-Judge-evaluated.
# ---------------------------------------------------------------------------
def test_baseline_is_not_reevaluated(monkeypatch) -> None:
    """Every physical attempt must target an rc.2 case — never a v0.1 one."""
    seen: list[str] = []
    original = v2.evaluate_attempt

    def spy(case, repeat_index, attempt_index, judge_, judge_config):
        seen.append(case.prompt_version)
        return original(case, repeat_index, attempt_index, judge_, judge_config)

    monkeypatch.setattr(v2, "evaluate_attempt", spy)
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
    judge = ScriptedJudge(_flat_responses(run.candidate_run.cases))
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())

    assert seen, "no attempt was executed"
    # Not one v0.1 plan reached the Evaluator.
    assert set(seen) == {"v0.2-rc.2"}
    # 90 semantic repeats, first-attempt success each -> exactly 90 calls.
    # Re-evaluating the baseline too would be 180.
    assert len(seen) == 90
    assert judge.calls == 90


def test_manifest_declares_no_baseline_rerun(executed_rc2) -> None:
    run, _ = executed_rc2
    manifest = de.build_development_manifest(run)
    assert manifest["v0_1_generation_rerun"] is False
    assert manifest["v0_1_evaluation_rerun"] is False
    assert manifest["baseline_evaluation_run"] == BASELINE_EVALUATION_RUN_ID
    assert manifest["candidate_generation_run"] == RC2_GENERATION_RUN_ID


# ---------------------------------------------------------------------------
# 8-9. Frozen acquisition policy.
# ---------------------------------------------------------------------------
def test_rc2_planned_semantic_repeats_is_90(prepared_rc2) -> None:
    cand = prepared_rc2.candidate_run
    assert cand.planned_semantic_repeats == 90
    assert cand.semantic_repeats_per_case == 3
    assert len(cand.cases) == 30


def test_rc2_max_physical_attempts_is_3(prepared_rc2) -> None:
    cand = prepared_rc2.candidate_run
    assert cand.max_attempts_per_semantic_repeat == 3
    assert cand.max_possible_physical_attempts == 270


def test_rc2_reuses_the_frozen_retry_taxonomy(prepared_rc2) -> None:
    manifest = de.build_development_manifest(prepared_rc2)
    assert manifest["retryable_failure_types"] == list(v2.RETRYABLE_FAILURE_TYPES)
    assert manifest["non_retryable_failure_types"] == list(
        v2.NON_RETRYABLE_FAILURE_TYPES
    )
    assert manifest["evaluator_retry_enabled"] is v2.EVALUATOR_RETRY_ENABLED
    assert manifest["attempt_retry_enabled"] is v2.BASELINE_ATTEMPT_RETRY_ENABLED
    assert manifest["max_attempts_per_semantic_repeat"] == (
        v2.MAX_ATTEMPTS_PER_SEMANTIC_REPEAT
    )
    # Imported, never redesigned — identity, not just equality.
    assert de.RETRYABLE_FAILURE_TYPES is v2.RETRYABLE_FAILURE_TYPES
    assert de.NON_RETRYABLE_FAILURE_TYPES is v2.NON_RETRYABLE_FAILURE_TYPES


def test_rc2_execution_rejects_a_redesigned_attempt_policy(prepared_rc2) -> None:
    judge = ScriptedJudge([])
    with pytest.raises(ValueError, match="Protocol v0.2 Section 7"):
        de.execute_candidate_evaluation(prepared_rc2, judge, max_attempts=5)


# ---------------------------------------------------------------------------
# 10. Eligibility logic is unchanged.
# ---------------------------------------------------------------------------
def test_rc2_plan_eligibility_is_at_least_2_of_3(executed_rc2) -> None:
    run, _ = executed_rc2
    assert v1.MIN_SUCCESSFUL_REPEATS == 2
    for case in run.candidate_run.cases:
        assert v1.case_eligible(run.candidate_run.records, case.case_id) is True


def test_rc2_pair_eligibility_intersects_both_sides(executed_rc2) -> None:
    run, _ = executed_rc2
    rows = de.case_pair_rows(run)
    assert len(rows) == 30
    # The frozen v0.1 baseline has 4 operationally-ineligible cases; the rc.2
    # side is healthy for all 30. Pair eligibility is the intersection: 26.
    # rc.2 success never triggers a v0.1 rerun, so those 4 stay excluded.
    eligible = [r for r in rows if r["pair_eligible"]]
    excluded = [r for r in rows if not r["pair_eligible"]]
    assert len(eligible) == 26
    assert len(excluded) == 4
    assert all(r["exclusion_reason"] == "v0_1_side_ineligible" for r in excluded)
    assert sorted(r["case_id"] for r in excluded) == FROZEN_BASELINE_INELIGIBLE

    comparison = de.build_paired_comparison(run, rows)
    coverage = comparison["coverage"]
    assert coverage["total_cases"] == 30
    assert coverage["v0_1_eligible"] == 26
    assert coverage["rc_2_eligible"] == 30
    assert coverage["pair_eligible"] == 26
    assert coverage["v0_1_side_rerun"] is False
    assert coverage["v0_1_side_reevaluated"] is False


def test_rc2_pair_eligibility_excludes_an_rc2_failure() -> None:
    """An rc.2 side with < 2 successful repeats is excluded; v0.1 is NOT rerun."""
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
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
    assert victim_row["rc_2_eligible"] is False
    assert victim_row["v0_1_eligible"] is True
    assert victim_row["pair_eligible"] is False
    assert victim_row["exclusion_reason"] == "rc_2_side_ineligible"
    # The failed side's delta is undefined — not a fabricated 0.
    assert victim_row["delta_D5"] is None

    coverage = de.build_paired_comparison(run, rows)["coverage"]
    # 26 baseline-eligible cases minus the rc.2 victim = 25 pairs.
    assert coverage["pair_eligible"] == 25
    assert len(coverage["excluded_case_ids"]) == 5
    assert victim in coverage["excluded_case_ids"]
    assert len(
        [
            e
            for e in coverage["exclusions"]
            if e["exclusion_reason"] == "v0_1_side_ineligible"
        ]
    ) == 4


def test_rc2_delta_is_candidate_minus_v0_1() -> None:
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
    # D5 lowered to 2 (a valid rubric score) so the delta is non-trivially
    # negative rather than a constant 0.
    rc2_scores = _scores(4, D5=2)
    judge = ScriptedJudge(
        _flat_responses(run.candidate_run.cases, scores=rc2_scores)
    )
    de.execute_candidate_evaluation(run, judge, sleep_fn=RecordingSleeper())

    rows = de.case_pair_rows(run)
    assert all(row["rc_2_D5"] == pytest.approx(2.0) for row in rows)

    paired = [r for r in rows if r["pair_eligible"]]
    assert len(paired) == 26
    for row in paired:
        v01_d5 = run.baseline.case_rows[row["case_id"]]["dimension_means"]["D5"]
        assert row["delta_D5"] == pytest.approx(round(2.0 - v01_d5, 4))
    assert all(r["delta_D5"] is None for r in rows if not r["pair_eligible"])

    stats = de.dimension_paired_stats(rows, "D5", "rc_2")
    assert stats["dimension"] == "D5"
    assert stats["n"] == 26
    assert stats["rc_2_mean"] == pytest.approx(2.0)
    assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"]
    assert stats["improved"] + stats["tied"] + stats["worsened"] == 26


# ---------------------------------------------------------------------------
# 11. A failed semantic repeat is never scored as 0.
# ---------------------------------------------------------------------------
def test_rc2_failed_semantic_repeat_is_not_scored_zero() -> None:
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.2")
    victim = run.candidate_run.cases[0].case_id
    # repeat 3 fails all three attempts; repeats 1-2 succeed with D5 = 2.
    spec = {(victim, 3): [_parse_error_payload()] * 3}
    scores = _scores(4, D5=2)
    judge = ScriptedJudge(
        _flat_responses(run.candidate_run.cases, spec=spec, scores=scores)
    )
    sleeper = RecordingSleeper()
    de.execute_candidate_evaluation(run, judge, sleep_fn=sleeper)

    row = next(r for r in de.case_pair_rows(run) if r["case_id"] == victim)
    # 2/3 successful -> still eligible.
    assert row["rc_2_successful_repeats"] == 2
    assert row["rc_2_eligible"] is True
    # Mean over the TWO successful repeats: 2.0. Zero-filling would give 1.3333.
    assert row["rc_2_D5"] == pytest.approx(2.0)
    assert row["rc_2_D5"] != pytest.approx(2.0 * 2 / 3)

    repeats = [
        r for r in run.candidate_run.repeat_results if r.case_id == victim
    ]
    victim_repeat_3 = next(r for r in repeats if r.repeat_index == 3)
    assert victim_repeat_3.semantic_repeat_success is False
    assert victim_repeat_3.attempt_count == 3
    assert len(victim_repeat_3.attempts) == 3
    # Backoff applied twice between three attempts, never a 4th.
    assert len(sleeper.delays) == 2
    assert len([r for r in repeats if r.semantic_repeat_success]) == 2


# ---------------------------------------------------------------------------
# Delivery behaviour must ride along with D5 (Section 7).
# ---------------------------------------------------------------------------
def test_rc2_delivery_behavior_is_reported(prepared_rc2) -> None:
    delivery = de.summarize_candidate_delivery_behavior(prepared_rc2)
    assert delivery["total_cases"] == 30
    assert delivery["empty_count"] == RC2_EMPTY
    assert delivery["non_empty_count"] == RC2_NON_EMPTY
    assert delivery["non_empty_case_ids"] == RC2_NON_EMPTY_IDS
    assert delivery["without_parsed_plan"] == 0
    assert delivery["prompt_version"] == "v0.2-rc.2"
    assert delivery["generation_run_id"] == RC2_GENERATION_RUN_ID
    # Corrective feedback: 2 non-empty; scaffolding: 1 non-empty.
    assert delivery["by_intent"]["corrective_feedback"]["non_empty"] == 2
    assert delivery["by_intent"]["scaffolding"]["non_empty"] == 1


def test_summary_and_comparison_carry_delivery_behavior(executed_rc2) -> None:
    run, _ = executed_rc2
    rows = de.case_pair_rows(run)
    summary = de.build_development_summary(run, rows)
    assert summary["delivery_behavior"]["empty_count"] == RC2_EMPTY
    assert summary["delivery_behavior"]["non_empty_count"] == RC2_NON_EMPTY
    assert summary["delivery_behavior"]["non_empty_case_ids"] == RC2_NON_EMPTY_IDS
    assert summary["candidate_prompt_version"] == "v0.2-rc.2"
    assert summary["candidate_generation_run"] == RC2_GENERATION_RUN_ID

    comparison = summary["paired_comparison"]
    assert comparison["delivery_behavior"]["empty_count"] == RC2_EMPTY
    assert comparison["delivery_behavior"]["non_empty_count"] == RC2_NON_EMPTY
    # The joint-judgement guard: D5 alone is explicitly not accepted.
    assert "D5" in comparison["delivery_behavior"]["must_be_read_with"]
    assert "mode collapse" in (
        comparison["delivery_behavior"]["joint_judgement_note"].lower()
    )
    assert any(
        "mode collapse" in q.lower()
        for q in comparison["interpretation"]["questions"]
    )
    assert "summary.delivery_behavior" in (
        comparison["interpretation"]["must_be_read_together_with"]
    )
    # No mechanical verdict anywhere.
    assert summary["verdict"] is None
    assert comparison["primary"]["threshold"] is None


def test_rc1_delivery_behavior_collapse_is_visible() -> None:
    """The rc.1 side measures 30/0 — the collapse rc.2 was written to break."""
    run = de.prepare_development_evaluation(prompt_version="v0.2-rc.1")
    delivery = de.summarize_candidate_delivery_behavior(run)
    assert delivery["empty_count"] == 30
    assert delivery["non_empty_count"] == 0
    assert delivery["non_empty_case_ids"] == []


# ---------------------------------------------------------------------------
# 12. dry-run makes no API call.
# ---------------------------------------------------------------------------
def test_cli_rc2_dry_run_makes_no_api_call() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--dry-run",
            "--prompt-version",
            "v0.2-rc.2",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "baseline population = 30" in out
    assert "candidate population = 30" in out
    assert "case IDs exact match = True" in out
    assert "input fingerprints match = True" in out
    assert f"baseline evaluation run = {BASELINE_EVALUATION_RUN_ID}" in out
    assert f"candidate generation run = {RC2_GENERATION_RUN_ID}" in out
    assert "candidate prompt = v0.2-rc.2" in out
    assert "Evaluator = v0.1" in out
    assert "Judge = qwen/qwen3.5-plus-20260420" in out
    assert "semantic repeats = 3" in out
    assert "max physical attempts = 3" in out
    assert "planned candidate semantic evaluations = 90" in out
    assert "maximum candidate physical Judge calls = 270" in out
    assert "No API call was made." in out


def test_cli_rc1_dry_run_still_defaults_to_rc1() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert "candidate prompt = v0.2-rc.1" in proc.stdout
    assert "candidate generation run = 20260831-052126" in proc.stdout


def test_cli_rejects_an_unknown_prompt_version() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--dry-run",
            "--prompt-version",
            "v0.2-rc.3",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode != 0
    assert "invalid choice" in (proc.stderr + proc.stdout)


def test_dry_run_never_constructs_a_judge(monkeypatch) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("dev_eval_cli_rc2", CLI)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def explode():
        raise AssertionError("dry-run must never build a Judge")

    monkeypatch.setattr(module, "build_baseline_judge", explode)
    assert module.main(["--dry-run", "--prompt-version", "v0.2-rc.2"]) == 0


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------
def test_rc2_artifacts_are_written(executed_rc2, tmp_path) -> None:
    run, _ = executed_rc2
    out = tmp_path / "rc2_run"
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
    assert manifest["candidate_prompt_version"] == "v0.2-rc.2"
    assert manifest["candidate_generation_run"] == RC2_GENERATION_RUN_ID
    assert manifest["baseline_evaluation_run"] == BASELINE_EVALUATION_RUN_ID
    assert manifest["case_ids_exact_match"] is True
    assert manifest["input_fingerprints_match"] is True
    assert manifest["planned_candidate_semantic_evaluations"] == 90
    assert manifest["maximum_candidate_physical_judge_calls"] == 270

    # evaluations.jsonl: one record per semantic repeat, attempts embedded.
    lines = (out / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 90
    assert json.loads(lines[0])["attempts"], "every physical attempt is preserved"

    # paired_comparison.csv is labelled rc_2 and keeps the same delta shape.
    with (out / "paired_comparison.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert "rc_2_D5" in rows[0]
    assert "v0_1_D5" in rows[0]
    assert "delta_D5" in rows[0]
    assert "rc_2_eligible" in rows[0]
    # 26 pair-eligible cases carry a delta; the 4 frozen baseline-ineligible
    # cases carry an empty delta (never a fabricated 0).
    assert sum(1 for r in rows if r["delta_D5"] != "") == 26
    assert sum(1 for r in rows if r["delta_D5"] == "") == 4

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] is None
    comparison = summary["paired_comparison"]
    assert comparison["primary"]["dimension"] == "D5"
    assert comparison["secondary"]["dimension"] == "D4"
    assert set(comparison["protected"]) == {"D1", "D2", "D3", "D6"}
    assert comparison["interpretation"]["is_confirmatory"] is False
    # Protected / secondary stats use the rc_2 label.
    assert "rc_2_mean" in comparison["primary"]
    assert "rc_2_mean" in comparison["protected"]["D1"]


def test_rc2_results_root_is_used_by_the_cli(monkeypatch) -> None:
    """``--execute`` writes under the rc.2 evaluation root, never the rc.1 one."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("dev_eval_cli_rc2_exec", CLI)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    captured: dict[str, object] = {}

    class _FakeJudge:
        provider = v2.FROZEN_JUDGE_PROVIDER
        model = v2.FROZEN_JUDGE_MODEL_REQUESTED
        structured_output_enabled = False

        def complete(self, system, user, *, temperature=0.0):
            raise AssertionError("this test must never reach the Judge")

    def fake_execute(run, judge, **kwargs):
        # Stands in for the real evaluation: no Judge call, no API, no sleeps.
        run.dry_run = False
        run.completed_at = "2026-08-31T00:00:00Z"

    monkeypatch.setattr(module, "build_baseline_judge", lambda: _FakeJudge())
    monkeypatch.setattr(module, "execute_candidate_evaluation", fake_execute)
    monkeypatch.setattr(
        module,
        "write_development_artifacts",
        lambda run, out_dir: captured.setdefault("out_dir", out_dir),
    )
    monkeypatch.setattr(module, "case_pair_rows", lambda run: [])
    monkeypatch.setattr(
        module,
        "summarize_candidate_delivery_behavior",
        lambda run: {"empty_count": RC2_EMPTY, "non_empty_count": RC2_NON_EMPTY},
    )

    assert module.main(["--execute", "--prompt-version", "v0.2-rc.2"]) == 0
    out_dir = Path(captured["out_dir"])
    assert out_dir.parent == de.evaluation_results_root_for_prompt_version(
        "v0.2-rc.2"
    )
    assert out_dir.parent != de.RESULTS_ROOT


def test_frozen_inputs_are_never_written() -> None:
    """The paired evaluation never writes into the two source runs."""
    assert de.RESULTS_ROOT_RC2.name == "prompt_v0_2_rc2_development_evaluation"
    assert de.RESULTS_ROOT_RC2 != de.BASELINE_EVALUATION_ROOT
    assert de.RESULTS_ROOT_RC2 != de.CANDIDATE_GENERATION_ROOT_RC2
    # The rc.2 generation run (frozen, QC'd) is untouched on disk.
    rc2_root = de.candidate_generation_root_for_prompt_version("v0.2-rc.2")
    assert rc2_root.is_dir()
    manifest = json.loads((rc2_root / "run_manifest.json").read_text("utf-8"))
    assert manifest["run_id"] == RC2_GENERATION_RUN_ID
    assert manifest["prompt_version"] == "v0.2-rc.2"
