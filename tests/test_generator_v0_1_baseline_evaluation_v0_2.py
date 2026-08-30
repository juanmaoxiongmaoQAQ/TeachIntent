"""Offline tests for the Generator v0.1 Baseline Evaluation Protocol **v0.2**.

v0.2 is an operational revision: it separates **semantic repeats** (frozen at
3 per case) from **physical attempts** (at most 3 per semantic repeat, used only
when the previous attempt failed to form a legal Evaluator artifact).

Coverage mirrors the 30 requirements in
``docs/generator_v0.1_evaluation_protocol_v0.2.md`` Section 21:

 1. exactly 3 semantic repeats            16. evidence_source_error retryable
 2. semantic repeat indexes 1/2/3         17. internal_evaluator_error NOT retryable
 3. attempt indexes 1/2/3                 18. setup errors NOT retryable
 4. first-attempt success -> stop         19. eligibility counts semantic repeats
 5. retryable failure -> retry            20. failed attempts never score 0
 6. success on attempt 2 -> stop          21. aggregation unchanged vs v0.1
 7. success on attempt 3 -> stop          22. attempt logs keep every failure
 8. 3 failures -> repeat fails            23. first_attempt_success_rate
 9. no attempt 4                          24. retry_recovery_rate
10. low valid score -> no retry           25. exhausted repeat count
11. critical flag -> no retry             26. source_population_sha256 unchanged
12. judge_api_error retryable             27. v0.1 protocol unchanged
13. judge_response_parse_error retryable  28. v0.1 runner behaviour unchanged
14. judge_output_schema_error retryable   29. dry-run makes no API call
15. evidence_grounding_error retryable    30. missing API key -> formal fail-fast

No Judge API call is ever made: every execution test uses a scripted offline
judge with precomputed, evidence-grounded (or deliberately invalid) responses.
Backoff is injected as a recording sleeper — tests never wait in real time.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from teachintent.evaluator import JudgeCompletion, compute_overall_score
from teachintent.evaluator.errors import JudgeAPIError
from teachintent.evaluator.rubric import DIMENSION_IDS
from teachintent.generator_evaluation import baseline_v0_1 as v1
from teachintent.generator_evaluation import baseline_v0_2 as v2

D = DIMENSION_IDS

REPO_ROOT = Path(__file__).resolve().parents[1]
V0_1_DOC = REPO_ROOT / "docs" / "generator_v0.1_evaluation_protocol_v0.1.md"
V0_2_DOC = REPO_ROOT / "docs" / "generator_v0.1_evaluation_protocol_v0.2.md"
V0_1_CLI = (
    REPO_ROOT / "scripts" / "run_generator_v0_1_baseline_evaluation.py"
)
V0_2_CLI = (
    REPO_ROOT / "scripts" / "run_generator_v0_1_baseline_evaluation_v0_2.py"
)
# SHA256 of the v0.1 protocol document as recorded by Protocol v0.1 Run 1
# (results/generator_v0_1_baseline_evaluation/20260830T063227Z/run_manifest.json).
# If the v0.1 document is edited after that run, this value stops matching.
V0_1_DOC_SHA256_AT_RUN_1 = (
    "4503ae3c8b4d2d7157f85a1aa39f849f6061be368e4d55e69eb5ea2892e9f673"
)
# SHA256 of the *Draft* revision of the v0.2 protocol document (2026-08-30).
# VOID as of the freeze: the frozen text differs (Status header + Sections 17 /
# 19.1 / 22 / 23), so this value must never appear in a run manifest again.
DRAFT_PROTOCOL_DOC_SHA256 = (
    "30bcc77df1f3a48357d65aefa20881012ddba2c7fd8dd78e7b8710111eafbb01"
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
def _scores(value: int = 4, **overrides: int) -> dict[str, int]:
    base = {d: value for d in D}
    base.update(overrides)
    return base


def _grounded_text(plan_doc: dict) -> str:
    """A 40-char prefix of the plan's canonical JSON — always grounded."""
    return json.dumps(
        plan_doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )[:40]


def _valid_payload(
    plan_doc: dict, scores: dict[str, int] | None = None, flags=()
) -> str:
    """A legal, evidence-grounded JudgeOutput JSON payload."""
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


def _parse_error_payload() -> str:
    """Not parseable as the JudgeOutput contract -> judge_response_parse_error."""
    return "I am afraid I cannot do that; here is prose instead of JSON."


def _schema_error_payload() -> str:
    """Valid JSON that violates the JudgeOutput shape -> judge_output_schema_error."""
    return json.dumps({"scores": {}, "critical_flags": []}, ensure_ascii=False)


def _evidence_source_error_payload() -> str:
    """Unresolvable evidence source -> evidence_source_error."""
    return json.dumps(
        {
            "scores": {
                d: {
                    "score": 4,
                    "evidence": [
                        {"source": "plan.no_such_field", "text": "anything"}
                    ],
                    "brief_justification": "ok",
                }
                for d in D
            },
            "critical_flags": [],
        },
        ensure_ascii=False,
    )


def _grounding_error_payload() -> str:
    """Evidence text absent from the resolved source -> evidence_grounding_error."""
    return json.dumps(
        {
            "scores": {
                d: {
                    "score": 4,
                    "evidence": [
                        {"source": "plan", "text": "ZZZ_NOT_GROUNDED_ZZZ"}
                    ],
                    "brief_justification": "ok",
                }
                for d in D
            },
            "critical_flags": [],
        },
        ensure_ascii=False,
    )


class ScriptedJudge:
    """Deterministic offline judge: one precomputed response per call, in order.

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

    @property
    def total(self) -> float:
        return sum(self.delays)


def _flat_responses(cases, spec: dict | None = None) -> list:
    """Build the flat response queue consumed in execution order.

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
                out.append(_valid_payload(plan_doc))
            else:
                out.extend(seq)
    return out


def _load_cli_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"cli_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _v0_2_result_dirs() -> set[str]:
    """Snapshot of existing v0.2 result run directories (for no-side-effect
    assertions that stay valid after a future formal run)."""
    root = REPO_ROOT / "results" / "generator_v0_1_baseline_evaluation_v0_2"
    if not root.is_dir():
        return set()
    return {p.name for p in root.iterdir() if p.is_dir()}


def _env_without_key() -> dict:
    env = dict(os.environ)
    env.pop("OPENROUTER_API_KEY", None)
    return env


# ---------------------------------------------------------------------------
# Protocol identity + taxonomy.
# ---------------------------------------------------------------------------
def test_protocol_v0_2_identity_and_status_is_frozen():
    assert v2.PROTOCOL_VERSION == "v0.2"
    assert v2.PROTOCOL_STATUS == "Frozen"
    assert v2.PROTOCOL_DOC_PATH == V0_2_DOC
    assert V0_2_DOC.is_file()
    text = V0_2_DOC.read_text(encoding="utf-8")
    assert "Status: Frozen" in text
    assert "Status: Draft" not in text
    # The freeze date is recorded in the document itself.
    assert "Frozen |" in text
    assert "2026-08-30" in text


def test_protocol_v0_2_document_sha_is_recomputed_from_the_frozen_text():
    """The manifest SHA must always be derived from the *current* doc bytes."""
    run = v2.prepare_baseline_run_v2()
    assert run.protocol_document_sha256 == _sha256(V0_2_DOC)
    # Guard against a stale hard-coded Draft-revision SHA.
    assert run.protocol_document_sha256 != DRAFT_PROTOCOL_DOC_SHA256
    assert len(run.protocol_document_sha256) == 64


def test_retryable_and_non_retryable_taxonomies_are_frozen_and_disjoint():
    assert v2.RETRYABLE_FAILURE_TYPES == (
        "judge_api_error",
        "judge_response_parse_error",
        "judge_output_schema_error",
        "evidence_source_error",
        "evidence_grounding_error",
    )
    assert v2.NON_RETRYABLE_FAILURE_TYPES == (
        "setup_input_jsonschema_error",
        "setup_input_pydantic_error",
        "setup_run_context_error",
        "setup_judge_config_error",
        "internal_evaluator_error",
    )
    assert not set(v2.RETRYABLE_FAILURE_TYPES) & set(
        v2.NON_RETRYABLE_FAILURE_TYPES
    )
    for failure_type in v2.RETRYABLE_FAILURE_TYPES:
        assert v2.is_retryable_failure(failure_type) is True
    for failure_type in v2.NON_RETRYABLE_FAILURE_TYPES:
        assert v2.is_retryable_failure(failure_type) is False
    # Layer-0 gate failures and unknown types are never retried.
    assert v2.is_retryable_failure("gate_json_schema") is False
    assert v2.is_retryable_failure(None) is False


def test_evaluator_retry_and_baseline_attempt_retry_are_distinct():
    """Evaluator v0.1 internal retry stays disabled; the runner retry is on."""
    assert v2.EVALUATOR_RETRY_ENABLED is False
    assert v2.EVALUATOR_RETRY_ENABLED is v1.FROZEN_RETRY_ENABLED
    assert v2.BASELINE_ATTEMPT_RETRY_ENABLED is True


def test_backoff_policy_is_frozen_and_bounded():
    assert v2.RETRY_BACKOFF_SECONDS["judge_api_error"] == (5.0, 15.0)
    assert v2.RETRY_BACKOFF_SECONDS["DEFAULT"] == (2.0, 2.0)
    assert v2.backoff_seconds("judge_api_error", 1) == 5.0
    assert v2.backoff_seconds("judge_api_error", 2) == 15.0
    assert v2.backoff_seconds("judge_response_parse_error", 1) == 2.0
    assert v2.backoff_seconds("judge_response_parse_error", 2) == 2.0
    assert v2.backoff_seconds("evidence_grounding_error", 1) == 2.0
    # No sleep before attempt 1, and none after attempt 3 (there is no attempt 4).
    assert v2.backoff_seconds("judge_api_error", 3) == 0.0


def test_design_budget_separates_semantic_repeats_from_physical_attempts():
    assert v2.PLANNED_SEMANTIC_REPEATS == 90
    assert v2.MAX_ATTEMPTS_PER_SEMANTIC_REPEAT == 3
    assert v2.MAX_POSSIBLE_PHYSICAL_ATTEMPTS == 270
    # 270 is a worst-case bound, never the size of the experiment.
    assert v2.PLANNED_SEMANTIC_REPEATS == v1.EXPECTED_CALLS == 90


# ---------------------------------------------------------------------------
# 1-3. Semantic repeat / attempt structure.
# ---------------------------------------------------------------------------
def test_exactly_three_semantic_repeats_per_case():
    run = v2.prepare_baseline_run_v2()
    assert len(run.cases) == 30
    plan = v2.plan_semantic_repeats(run.cases)
    assert len(plan) == 90
    per_case = Counter(entry["case_id"] for entry in plan)
    assert len(per_case) == 30
    assert all(n == 3 for n in per_case.values())


def test_semantic_repeat_indexes_are_1_2_3():
    run = v2.prepare_baseline_run_v2()
    judge = ScriptedJudge(_flat_responses(run.cases))
    v2.execute_baseline_run_v2(run, judge)
    assert len(run.repeat_results) == 90
    assert {r.repeat_index for r in run.repeat_results} == {1, 2, 3}
    for case in run.cases:
        repeats = sorted(
            r.repeat_index for r in run.repeat_results if r.case_id == case.case_id
        )
        assert repeats == [1, 2, 3]


def test_attempt_indexes_are_1_2_3():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    # attempt 1 parse error, attempt 2 grounding error, attempt 3 valid.
    responses = [
        _parse_error_payload(),
        _grounding_error_payload(),
        _valid_payload(plan_doc),
    ]
    judge = ScriptedJudge(responses)
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert [a.attempt_index for a in outcome.attempts] == [1, 2, 3]
    assert outcome.attempt_count == 3


# ---------------------------------------------------------------------------
# 4-9. Retry termination rules.
# ---------------------------------------------------------------------------
def test_first_attempt_success_stops_immediately():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge([_valid_payload(plan_doc), _valid_payload(plan_doc)])
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.semantic_repeat_success is True
    assert outcome.successful_attempt_index == 1
    assert outcome.attempt_count == 1
    assert outcome.stopped_reason == v2.STOPPED_VALID_ARTIFACT
    # The second queued response was never consumed.
    assert judge.calls == 1


def test_retryable_failure_triggers_retry():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    sleeper = RecordingSleeper()
    judge = ScriptedJudge([_parse_error_payload(), _valid_payload(plan_doc)])
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge), sleep_fn=sleeper
    )
    assert judge.calls == 2
    assert outcome.semantic_repeat_success is True
    assert outcome.successful_attempt_index == 2
    assert outcome.attempt_failure_types == ("judge_response_parse_error",)
    assert sleeper.delays == [2.0]


def test_success_on_attempt_2_stops():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge(
        [_parse_error_payload(), _valid_payload(plan_doc), _valid_payload(plan_doc)]
    )
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.successful_attempt_index == 2
    assert outcome.attempt_count == 2
    assert judge.calls == 2


def test_success_on_attempt_3_stops():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge(
        [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _valid_payload(plan_doc),
            _valid_payload(plan_doc),
        ]
    )
    sleeper = RecordingSleeper()
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge), sleep_fn=sleeper
    )
    assert outcome.successful_attempt_index == 3
    assert outcome.attempt_count == 3
    assert outcome.attempt_failure_types == (
        "evidence_grounding_error",
        "evidence_grounding_error",
    )
    assert judge.calls == 3
    # Backoff before attempt 2 and before attempt 3 only.
    assert sleeper.delays == [2.0, 2.0]


def test_three_failures_fail_the_semantic_repeat_and_no_fourth_attempt():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge(
        [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
            _valid_payload(plan_doc),  # must NEVER be consumed (attempt 4)
        ]
    )
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.semantic_repeat_success is False
    assert outcome.successful_attempt_index is None
    assert outcome.final_artifact is None
    assert outcome.attempt_count == 3
    assert outcome.stopped_reason == v2.STOPPED_EXHAUSTED
    assert len(outcome.attempt_failure_types) == 3
    # A 4th attempt is prohibited.
    assert judge.calls == 3


def test_execute_run_rejects_max_attempts_other_than_three():
    run = v2.prepare_baseline_run_v2()
    judge = ScriptedJudge([])
    for bad in (0, 1, 2, 4):
        with pytest.raises(ValueError, match="max_attempts must be exactly 3"):
            v2.execute_baseline_run_v2(run, judge, max_attempts=bad)


# ---------------------------------------------------------------------------
# 10-11. A legal artifact is accepted whatever it contains.
# ---------------------------------------------------------------------------
def test_low_valid_score_never_triggers_retry():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    # Lowest possible legal scores (all 1) plus an extra queued response.
    judge = ScriptedJudge(
        [_valid_payload(plan_doc, _scores(1)), _valid_payload(plan_doc, _scores(4))]
    )
    sleeper = RecordingSleeper()
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge), sleep_fn=sleeper
    )
    assert outcome.semantic_repeat_success is True
    assert judge.calls == 1
    assert sleeper.delays == []
    assert outcome.final_artifact["overall_score"] == compute_overall_score(
        _scores(1)
    )


def test_critical_flag_never_triggers_retry():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    flag = "material_off_anchor_content"
    assert flag in v1.CRITICAL_FLAGS
    judge = ScriptedJudge(
        [
            _valid_payload(plan_doc, _scores(1), flags=(flag,)),
            _valid_payload(plan_doc, _scores(4)),
        ]
    )
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    # A raised critical flag is a RESULT, never a retry condition.
    assert outcome.semantic_repeat_success is True
    assert judge.calls == 1
    assert [cf["flag"] for cf in outcome.final_artifact["critical_flags"]] == [flag]


# ---------------------------------------------------------------------------
# 12-16. Every retryable failure type is retried.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "failure_payload, expected_failure_type",
    [
        (JudgeAPIError("simulated api failure"), "judge_api_error"),
        (_parse_error_payload(), "judge_response_parse_error"),
        (_schema_error_payload(), "judge_output_schema_error"),
        (_evidence_source_error_payload(), "evidence_source_error"),
        (_grounding_error_payload(), "evidence_grounding_error"),
    ],
)
def test_each_retryable_failure_type_is_retried(
    failure_payload, expected_failure_type
):
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge([failure_payload, _valid_payload(plan_doc)])
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.attempts[0].failure_type == expected_failure_type
    assert outcome.attempts[0].retryable is True
    assert judge.calls == 2
    assert outcome.semantic_repeat_success is True
    assert outcome.successful_attempt_index == 2


def test_judge_api_error_uses_the_5_then_15_second_backoff():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge(
        [
            JudgeAPIError("simulated api failure"),
            JudgeAPIError("simulated api failure"),
            _valid_payload(plan_doc),
        ]
    )
    sleeper = RecordingSleeper()
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge), sleep_fn=sleeper
    )
    assert sleeper.delays == [5.0, 15.0]
    assert outcome.successful_attempt_index == 3
    # The tests never actually waited: total requested delay is recorded only.
    assert sleeper.total == 20.0


# ---------------------------------------------------------------------------
# 17-18. Non-retryable failures stop the semantic repeat.
# ---------------------------------------------------------------------------
def test_internal_evaluator_error_is_not_retryable():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    judge = ScriptedJudge(
        [RuntimeError("simulated evaluator bug"), _valid_payload(plan_doc)]
    )
    sleeper = RecordingSleeper()
    outcome = v2.execute_semantic_repeat(
        case, 1, judge, v2.build_frozen_judge_config(judge), sleep_fn=sleeper
    )
    assert outcome.attempts[0].failure_type == "internal_evaluator_error"
    assert outcome.attempts[0].retryable is False
    assert judge.calls == 1
    assert outcome.attempt_count == 1
    assert outcome.stopped_reason == v2.STOPPED_NON_RETRYABLE
    assert sleeper.delays == []


def test_setup_errors_are_not_retryable():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    # A structurally invalid input document fails at Evaluator setup step 4,
    # before any Judge call.
    broken = v1.CanonicalCase(
        **{**case.__dict__, "input_doc": {"not": "a valid TeachIntent input"}}
    )
    judge = ScriptedJudge([_valid_payload(json.loads(case.raw_response))])
    outcome = v2.execute_semantic_repeat(
        broken, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.attempts[0].failure_type == "setup_input_jsonschema_error"
    assert outcome.attempts[0].retryable is False
    assert judge.calls == 0
    assert outcome.attempt_count == 1
    assert outcome.semantic_repeat_success is False


def test_layer0_gate_failure_is_not_masked_by_a_judge_retry():
    """A canonical Generator output that fails Layer 0 is an invariant
    violation: it must be exposed, never retried away."""
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    broken = v1.CanonicalCase(**{**case.__dict__, "raw_response": "not json at all"})
    judge = ScriptedJudge([_valid_payload(json.loads(case.raw_response))])
    outcome = v2.execute_semantic_repeat(
        broken, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    assert outcome.attempts[0].failure_type == "gate_response_parse"
    assert outcome.attempts[0].retryable is False
    assert judge.calls == 0
    assert outcome.semantic_repeat_success is False
    assert outcome.stopped_reason == v2.STOPPED_NON_RETRYABLE


def test_non_retryable_failure_is_never_reported_as_retryable_in_metrics():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    broken = v1.CanonicalCase(**{**case.__dict__, "raw_response": "not json at all"})
    judge = ScriptedJudge([])
    outcome = v2.execute_semantic_repeat(
        broken, 1, judge, v2.build_frozen_judge_config(judge),
        sleep_fn=RecordingSleeper(),
    )
    metrics = v2.operational_attempt_metrics([outcome], planned=1)
    assert metrics["attempt_failure_taxonomy_counts"] == {
        "gate_response_parse": 1
    }
    assert metrics["non_retryable_terminations"] == 1
    assert metrics["retryable_first_attempt_failures"] == 0
    assert metrics["retry_recovery_rate"] is None


# ---------------------------------------------------------------------------
# 19-21. Eligibility, scoring and aggregation.
# ---------------------------------------------------------------------------
def test_case_eligibility_counts_semantic_repeats_not_attempts():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    spec = {
        # repeat 1: attempt 2 succeeds   -> semantic SUCCESS (2 attempts)
        (case.case_id, 1): [_parse_error_payload(), _valid_payload(plan_doc)],
        # repeat 2: attempt 1 succeeds   -> semantic SUCCESS (1 attempt)
        (case.case_id, 2): [_valid_payload(plan_doc)],
        # repeat 3: all 3 attempts fail  -> semantic FAILURE (3 attempts)
        (case.case_id, 3): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
    }
    # Only this case is evaluated; the other 29 keep their default responses.
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)

    assert v1.case_eligible(run.records, case.case_id) is True
    assert v1.successful_repeat_count(run.records, case.case_id) == 2
    diagnostics = v2.case_attempt_diagnostics(run.repeat_results, case.case_id)
    assert diagnostics["successful_semantic_repeats"] == 2
    assert diagnostics["failed_semantic_repeats"] == 1
    # 6 physical attempts, but only 2 of them are semantic successes.
    assert diagnostics["total_physical_attempts"] == 6
    assert diagnostics["first_attempt_successes"] == 1
    assert diagnostics["recovered_by_retry_count"] == 1
    assert diagnostics["exhausted_repeat_count"] == 1


def test_failed_attempts_never_contribute_score_zero():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    spec = {
        (case.case_id, 1): [
            _grounding_error_payload(),
            _valid_payload(plan_doc, _scores(4)),
        ],
        (case.case_id, 2): [_valid_payload(plan_doc, _scores(4))],
        (case.case_id, 3): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)

    means = v1.case_dimension_means(run.records, case.case_id)
    assert all(value == 4.0 for value in means.values())
    assert v1.case_overall_mean(run.records, case.case_id) == (
        round(compute_overall_score(_scores(4)), 4)
    )


def test_aggregation_is_identical_to_v0_1_for_the_same_semantic_outcomes():
    """Same 90 semantic artifacts -> identical v0.1 aggregation under v0.2."""
    responses = _flat_responses(v1.load_canonical_cases()[0])

    run_v1 = v1.prepare_baseline_run()
    judge_v1 = ScriptedJudge(list(responses))
    v1.execute_baseline_run(run_v1, judge_v1)
    agg_v1 = v1.aggregate(run_v1)

    run_v2 = v2.prepare_baseline_run_v2()
    judge_v2 = ScriptedJudge(list(responses))
    v2.execute_baseline_run_v2(run_v2, judge_v2)
    agg_v2 = v2.aggregate_v0_2(run_v2)

    assert judge_v1.calls == judge_v2.calls == 90
    assert agg_v2["intent"] == agg_v1["intent"]
    assert agg_v2["block"] == agg_v1["block"]

    global_v2 = dict(agg_v2["global"])
    operational = global_v2.pop("operational_attempt_metrics")
    assert global_v2 == agg_v1["global"]

    # Per-case semantic fields are identical; v0.2 only ADDS retry fields.
    for row_v1, row_v2 in zip(agg_v1["cases"], agg_v2["cases"]):
        for key, value in row_v1.items():
            assert row_v2[key] == value, (row_v1["case_id"], key)

    # And with an all-success run, 90 semantic repeats cost 90 attempts.
    assert operational["total_physical_attempts"] == 90
    assert operational["first_attempt_success_rate"] == 1.0


def test_case_weight_is_not_increased_by_extra_attempts():
    """A case rescued by retries still counts once in the global statistics."""
    run = v2.prepare_baseline_run_v2()
    victim = run.cases[0]
    plan_doc = json.loads(victim.raw_response)
    spec = {
        (victim.case_id, r): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _valid_payload(plan_doc, _scores(2)),
        ]
        for r in (1, 2, 3)
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)
    agg = v2.aggregate_v0_2(run)
    g = agg["global"]
    assert g["eligible_case_count"] == 30
    assert g["dimensions"]["D1"]["n"] == 30
    assert g["overall_score"]["n"] == 30
    # 3 semantic repeats rescued with 9 physical attempts, but n stays 30.
    assert g["operational_attempt_metrics"]["total_physical_attempts"] == 90 + 6


# ---------------------------------------------------------------------------
# 22. Attempt logging.
# ---------------------------------------------------------------------------
def test_attempt_logs_preserve_every_failure():
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    spec = {
        (case.case_id, 1): [
            _evidence_source_error_payload(),
            _grounding_error_payload(),
            _valid_payload(plan_doc),
        ],
        (case.case_id, 2): [_parse_error_payload(), _valid_payload(plan_doc)],
        (case.case_id, 3): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)

    rows = [r for r in run.repeat_results if r.case_id == case.case_id]
    rows.sort(key=lambda r: r.repeat_index)
    # Every attempt is retained; a later success never overwrites a failure.
    assert [r.attempt_count for r in rows] == [3, 2, 3]
    assert rows[0].attempt_failure_types == (
        "evidence_source_error",
        "evidence_grounding_error",
    )
    assert all(a.outcome == "failure" for a in rows[0].attempts[:2])
    assert rows[0].attempts[2].outcome == "artifact"
    assert rows[0].attempts[2].artifact is not None
    # Each failure keeps its own summary and metadata.
    for attempt in rows[0].attempts:
        assert attempt.started_at and attempt.completed_at
        assert attempt.run_metadata is not None
        assert attempt.judge_model_reported == v2.FROZEN_JUDGE_MODEL_REQUESTED
        assert attempt.block == case.block
        assert attempt.intent == case.intent
    assert rows[0].attempts[0].failure_summary
    assert rows[0].attempts[0].failure_type == "evidence_source_error"


def test_evaluations_jsonl_keeps_every_attempt(tmp_path):
    run = v2.prepare_baseline_run_v2()
    case = run.cases[0]
    plan_doc = json.loads(case.raw_response)
    spec = {
        (case.case_id, 1): [
            _grounding_error_payload(),
            _valid_payload(plan_doc),
        ],
        (case.case_id, 3): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)
    out = tmp_path / "run"
    v2.write_artifacts_v2(run, out, agg=v2.aggregate_v0_2(run))

    lines = [
        json.loads(line)
        for line in (out / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 90  # one record per semantic repeat
    row = next(line for line in lines if line["case_id"] == case.case_id and line["repeat_index"] == 1)
    assert row["semantic_repeat_success"] is True
    assert row["successful_attempt_index"] == 2
    assert [a["attempt_index"] for a in row["attempts"]] == [1, 2]
    assert row["attempts"][0]["failure_type"] == "evidence_grounding_error"
    assert row["attempts"][0]["outcome"] == "failure"
    assert row["attempts"][0]["artifact"] is None
    assert row["attempts"][1]["outcome"] == "artifact"

    exhausted = next(
        line for line in lines
        if line["case_id"] == case.case_id and line["repeat_index"] == 3
    )
    assert exhausted["semantic_repeat_success"] is False
    assert exhausted["successful_attempt_index"] is None
    assert len(exhausted["attempts"]) == 3
    assert exhausted["attempt_failure_types"] == ["evidence_grounding_error"] * 3


# ---------------------------------------------------------------------------
# 23-25. Operational attempt metrics.
# ---------------------------------------------------------------------------
def _mixed_repeat_results(case):
    """r1 recovered on attempt 2, r2 first-attempt success, r3 exhausted."""
    def make(repeat_index, attempts, success_index, reason, artifact):
        return v2.SemanticRepeatResult(
            case_id=case.case_id,
            block=case.block,
            intent=case.intent,
            repeat_index=repeat_index,
            semantic_repeat_success=success_index is not None,
            successful_attempt_index=success_index,
            attempt_count=len(attempts),
            attempt_failure_types=tuple(
                a.failure_type for a in attempts if a.failure_type
            ),
            final_artifact=artifact,
            stopped_reason=reason,
            attempts=tuple(attempts),
        )

    def attempt(index, failure_type):
        return v2.AttemptRecord(
            case_id=case.case_id,
            block=case.block,
            intent=case.intent,
            repeat_index=0,
            attempt_index=index,
            started_at="t0",
            completed_at="t1",
            outcome="failure" if failure_type else "artifact",
            failure_type=failure_type,
            failure_summary=None,
            artifact=None,
            judge_model_reported=None,
            run_metadata=None,
            retryable=v2.is_retryable_failure(failure_type),
        )

    return [
        make(
            1,
            [attempt(1, "judge_response_parse_error"), attempt(2, None)],
            2,
            v2.STOPPED_VALID_ARTIFACT,
            {"overall_score": 1.0},
        ),
        make(2, [attempt(1, None)], 1, v2.STOPPED_VALID_ARTIFACT, {"overall_score": 1.0}),
        make(
            3,
            [
                attempt(1, "judge_api_error"),
                attempt(2, "judge_api_error"),
                attempt(3, "judge_api_error"),
            ],
            None,
            v2.STOPPED_EXHAUSTED,
            None,
        ),
    ]


def test_operational_attempt_metrics_are_correct():
    case = v1.CanonicalCase(
        case_id="X-01", block="A", block_name="controlled_contrast",
        intent="elicitation", source_run_id="test-run", source_path="",
        input_doc={}, raw_response="", prompt_version="v0.1",
        generator_version="v0.1", requested_model=None, reported_model=None,
        generation_outcome="success",
    )
    results = _mixed_repeat_results(case)
    metrics = v2.operational_attempt_metrics(results, planned=3)

    assert metrics["planned_semantic_repeats"] == 3
    assert metrics["successful_semantic_repeats"] == 2
    assert metrics["failed_semantic_repeats"] == 1
    assert metrics["semantic_repeat_success_rate"] == round(2 / 3, 4)
    assert metrics["total_physical_attempts"] == 6
    assert metrics["successful_first_attempts"] == 1
    assert metrics["successful_after_retry"] == 1
    assert metrics["exhausted_after_max_attempts"] == 1
    assert metrics["mean_attempts_per_semantic_repeat"] == 2.0
    assert metrics["attempt_failure_taxonomy_counts"] == {
        "judge_api_error": 3,
        "judge_response_parse_error": 1,
    }
    assert metrics["max_possible_physical_attempts"] == 270
    assert metrics["actual_physical_attempts"] == 6


def test_first_attempt_success_rate_and_retry_recovery_rate_are_correct():
    case = v1.CanonicalCase(
        case_id="X-01", block="A", block_name="controlled_contrast",
        intent="elicitation", source_run_id="test-run", source_path="",
        input_doc={}, raw_response="", prompt_version="v0.1",
        generator_version="v0.1", requested_model=None, reported_model=None,
        generation_outcome="success",
    )
    metrics = v2.operational_attempt_metrics(_mixed_repeat_results(case), planned=3)
    # 1 of 3 semantic repeats succeeded on the FIRST attempt.
    assert metrics["first_attempt_success_rate"] == round(1 / 3, 4)
    # Denominator: semantic repeats whose attempt 1 failed RETRYABLY = 2 (r1, r3).
    assert metrics["retryable_first_attempt_failures"] == 2
    # Numerator: semantic repeats recovered by a retry = 1 (r1).
    assert metrics["retry_recovery_rate"] == 0.5


def test_retry_recovery_rate_is_none_without_a_retryable_first_failure():
    case = v1.CanonicalCase(
        case_id="X-01", block="A", block_name="controlled_contrast",
        intent="elicitation", source_run_id="test-run", source_path="",
        input_doc={}, raw_response="", prompt_version="v0.1",
        generator_version="v0.1", requested_model=None, reported_model=None,
        generation_outcome="success",
    )
    attempt = v2.AttemptRecord(
        case_id="X-01", block="A", intent="elicitation", repeat_index=1,
        attempt_index=1, started_at="t0", completed_at="t1", outcome="artifact",
        failure_type=None, failure_summary=None, artifact={},
        judge_model_reported=None, run_metadata=None, retryable=False,
    )
    clean = v2.SemanticRepeatResult(
        case_id="X-01", block="A", intent="elicitation", repeat_index=1,
        semantic_repeat_success=True, successful_attempt_index=1, attempt_count=1,
        attempt_failure_types=(), final_artifact={},
        stopped_reason=v2.STOPPED_VALID_ARTIFACT, attempts=(attempt,),
    )
    metrics = v2.operational_attempt_metrics([clean], planned=1)
    assert metrics["retryable_first_attempt_failures"] == 0
    assert metrics["successful_after_retry"] == 0
    assert metrics["retry_recovery_rate"] is None
    assert metrics["first_attempt_success_rate"] == 1.0


def test_exhausted_repeat_count_is_reported_per_case_and_globally():
    run = v2.prepare_baseline_run_v2()
    victim = run.cases[0]
    spec = {
        (victim.case_id, 1): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
        (victim.case_id, 2): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)
    agg = v2.aggregate_v0_2(run)

    diagnostics = v2.case_attempt_diagnostics(run.repeat_results, victim.case_id)
    assert diagnostics["exhausted_repeat_count"] == 2
    assert diagnostics["successful_semantic_repeats"] == 1
    assert diagnostics["failed_semantic_repeats"] == 2
    assert diagnostics["total_physical_attempts"] == 7
    assert diagnostics["attempt_failure_types"] == ["evidence_grounding_error"]

    assert agg["global"]["operational_attempt_metrics"][
        "exhausted_after_max_attempts"
    ] == 2
    # 2/3 semantic repeats lost -> case excluded.
    assert v1.case_eligible(run.records, victim.case_id) is False


# ---------------------------------------------------------------------------
# 26. Population fingerprint unchanged.
# ---------------------------------------------------------------------------
def test_source_population_sha256_is_unchanged_from_v0_1():
    assert v2.SOURCE_POPULATION_SHA256 is v1.SOURCE_POPULATION_SHA256
    assert v2.SOURCE_POPULATION_SHA256 == (
        "a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b"
    )
    cases, integrity = v1.load_canonical_cases()
    assert integrity.population_sha256 == v2.SOURCE_POPULATION_SHA256
    assert integrity.population_sha256_match is True
    run = v2.prepare_baseline_run_v2()
    assert run.source_population_sha256 == v2.SOURCE_POPULATION_SHA256
    assert run.source_population_sha256_expected == v2.SOURCE_POPULATION_SHA256
    assert run.source_population_sha256_match is True
    digest, matches = v1.verify_population_fingerprint(cases)
    assert digest == v2.SOURCE_POPULATION_SHA256 and matches is True


# ---------------------------------------------------------------------------
# 27-28. v0.1 protocol and runner are untouched.
# ---------------------------------------------------------------------------
def test_v0_1_protocol_document_is_unchanged_since_run_1():
    """Run 1 recorded the v0.1 document hash; it must still match."""
    assert _sha256(V0_1_DOC) == V0_1_DOC_SHA256_AT_RUN_1
    text = V0_1_DOC.read_text(encoding="utf-8")
    assert "**Status: Frozen**" in text
    # v0.1 must not have absorbed any v0.2 attempt-policy language.
    for forbidden in (
        "physical attempt",
        "MAX_ATTEMPTS_PER_SEMANTIC_REPEAT",
        "RETRYABLE_FAILURE_TYPES",
        "baseline_attempt_retry_enabled",
    ):
        assert forbidden not in text


def test_v0_1_runner_module_is_unchanged_by_v0_2():
    assert v1.PROTOCOL_VERSION == "v0.1"
    assert v1.PROTOCOL_STATUS == "Frozen"
    assert v1.EXPECTED_CALLS == 90
    assert v1.REPEATS == 3
    assert v1.MIN_SUCCESSFUL_REPEATS == 2
    # v0.1 execution still performs exactly one attempt per repeat: 90 calls,
    # no retry.
    run = v1.prepare_baseline_run()
    judge = ScriptedJudge(_flat_responses(run.cases))
    v1.execute_baseline_run(run, judge)
    assert judge.calls == 90
    assert len(run.records) == 90
    # The v0.1 source carries no v0.2 attempt-policy symbols.
    source = Path(v1.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "MAX_ATTEMPTS_PER_SEMANTIC_REPEAT",
        "RETRYABLE_FAILURE_TYPES",
        "physical attempt",
        "execute_semantic_repeat",
    ):
        assert forbidden not in source
    cli_source = V0_1_CLI.read_text(encoding="utf-8")
    for forbidden in (
        "max-attempts",
        "RETRYABLE_FAILURE_TYPES",
        "execute_baseline_run_v2",
    ):
        assert forbidden not in cli_source


# ---------------------------------------------------------------------------
# 29-30. CLI: dry-run makes no API call; formal mode fails fast without a key.
# ---------------------------------------------------------------------------
def test_dry_run_makes_no_api_call(monkeypatch, capsys):
    cli = _load_cli_module(V0_2_CLI)

    def explode(*args, **kwargs):  # pragma: no cover — must never be reached
        raise AssertionError("dry-run must never construct or call a Judge")

    monkeypatch.setattr(cli, "build_baseline_judge", explode)
    monkeypatch.setattr(cli, "execute_baseline_run_v2", explode)

    assert cli.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out
    for expected in (
        "Protocol version: v0.2",
        "Protocol status: Frozen",
        f"protocol_document_sha256 = {_sha256(V0_2_DOC)}",
        "A = 20260827-002543",
        "B = 20260827-051547",
        "C = 20260827-074602",
        "A/B/C = 12/12/6",
        "total cases = 30",
        "source_population_sha256 = "
        "a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b",
        "SHA match = True",
        "Generator = v0.1",
        "Prompt = v0.1",
        "Evaluator = v0.1",
        "Judge = qwen/qwen3.5-plus-20260420",
        "semantic repeats per case = 3",
        "planned semantic repeats = 90",
        "max attempts per semantic repeat = 3",
        "max possible physical attempts = 270",
        "baseline attempt retry = enabled",
        "- judge_api_error",
        "- judge_response_parse_error",
        "- judge_output_schema_error",
        "- evidence_source_error",
        "- evidence_grounding_error",
        "evaluator internal retry = disabled",
        "No Judge API call was made.",
    ):
        assert expected in printed, expected


def test_dry_run_subprocess_makes_no_api_call_and_writes_nothing(tmp_path):
    """End-to-end: the real CLI process, with the key removed from the env."""
    before = _v0_2_result_dirs()
    proc = subprocess.run(
        [sys.executable, str(V0_2_CLI), "--dry-run"],
        capture_output=True, text=True, env=_env_without_key(), cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert "No Judge API call was made." in proc.stdout
    assert v2.SOURCE_POPULATION_SHA256 in proc.stdout
    # dry-run must print the FROZEN protocol document SHA, freshly recomputed.
    frozen_sha = _sha256(V0_2_DOC)
    assert f"protocol_document_sha256 = {frozen_sha}" in proc.stdout
    assert DRAFT_PROTOCOL_DOC_SHA256 not in proc.stdout
    assert "Protocol status: Frozen" in proc.stdout
    assert "Protocol version: v0.2" in proc.stdout
    # No result run directory was created.
    assert _v0_2_result_dirs() == before


def test_frozen_protocol_document_sha_is_stable_and_current():
    """The frozen doc SHA must be computed live, never hard-coded from Draft."""
    first = v2.prepare_baseline_run_v2().protocol_document_sha256
    second = v2.prepare_baseline_run_v2().protocol_document_sha256
    assert first == second == _sha256(V0_2_DOC)
    assert first != DRAFT_PROTOCOL_DOC_SHA256
    assert v2.PROTOCOL_STATUS == "Frozen"


def test_formal_mode_without_api_key_fails_fast(monkeypatch, tmp_path, capsys):
    cli = _load_cli_module(V0_2_CLI)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def explode(*args, **kwargs):  # pragma: no cover — must never be reached
        raise AssertionError("formal mode must abort before executing the run")

    monkeypatch.setattr(cli, "execute_baseline_run_v2", explode)

    assert cli.main([]) == 2
    err = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in err
    assert "Aborting before any Judge call" in err
    # No result run directory is created.
    assert list(tmp_path.iterdir()) == []


def test_formal_mode_with_empty_api_key_fails_fast(monkeypatch, capsys):
    cli = _load_cli_module(V0_2_CLI)
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
    assert cli.main([]) == 2
    assert "Aborting before any Judge call" in capsys.readouterr().err


def test_formal_mode_subprocess_without_key_exits_2():
    before = _v0_2_result_dirs()
    proc = subprocess.run(
        [sys.executable, str(V0_2_CLI)],
        capture_output=True, text=True, env=_env_without_key(), cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 2
    assert "OPENROUTER_API_KEY" in proc.stderr
    # The key VALUE is never echoed.
    assert "OPENROUTER_API_KEY=" not in proc.stderr
    # No result run directory was created.
    assert _v0_2_result_dirs() == before


def test_cli_rejects_non_frozen_repeats_and_max_attempts():
    cli = _load_cli_module(V0_2_CLI)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--dry-run", "--repeats", "2"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["--dry-run", "--max-attempts", "2"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["--dry-run", "--max-attempts", "4"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Manifest / summary / artifact provenance.
# ---------------------------------------------------------------------------
def test_manifest_records_both_retry_concepts_and_the_attempt_policy():
    run = v2.prepare_baseline_run_v2()
    judge = ScriptedJudge(_flat_responses(run.cases))
    v2.execute_baseline_run_v2(run, judge)
    manifest = v2.build_manifest_v2(run)

    assert manifest["protocol_version"] == "v0.2"
    assert manifest["protocol_status"] == "Frozen"
    assert manifest["protocol_document_sha256"] == _sha256(V0_2_DOC)
    assert manifest["protocol_document_sha256"] != DRAFT_PROTOCOL_DOC_SHA256
    assert manifest["source_run_ids"] == [
        "20260827-002543",
        "20260827-051547",
        "20260827-074602",
    ]
    assert manifest["source_population_sha256"] == v2.SOURCE_POPULATION_SHA256
    assert manifest["source_population_sha256_expected"] == (
        v2.SOURCE_POPULATION_SHA256
    )
    assert manifest["source_population_sha256_match"] is True
    assert manifest["generator_version"] == "v0.1"
    assert "do not directly record generator_version" in (
        manifest["generator_version_provenance"]
    )
    assert manifest["prompt_version"] == "v0.1"
    assert "artifact_directly_recorded" in manifest["prompt_version_provenance"]
    assert manifest["evaluator_version"] == "v0.1"
    assert manifest["judge_prompt_version"] == "v0.1"
    assert len(manifest["judge_prompt_sha256"]) == 64
    assert manifest["judge_provider"] == "openrouter"
    assert manifest["judge_model_requested"] == "qwen/qwen3.5-plus-20260420"
    assert manifest["judge_model_reported"] == ["qwen/qwen3.5-plus-20260420"]
    assert manifest["temperature"] == 0
    assert manifest["structured_output_enabled"] is False
    assert manifest["self_repair_enabled"] is False
    # ---- The two retry concepts, recorded separately ----
    assert manifest["evaluator_retry_enabled"] is False
    assert manifest["baseline_attempt_retry_enabled"] is True
    assert manifest["max_attempts_per_semantic_repeat"] == 3
    assert manifest["retryable_failure_types"] == list(v2.RETRYABLE_FAILURE_TYPES)
    assert manifest["non_retryable_failure_types"] == list(
        v2.NON_RETRYABLE_FAILURE_TYPES
    )
    assert manifest["retry_backoff_policy"]["judge_api_error"] == [5.0, 15.0]
    # ---- Design: semantic repeats vs physical attempts ----
    assert manifest["case_count"] == 30
    assert manifest["semantic_repeats_per_case"] == 3
    assert manifest["planned_semantic_repeats"] == 90
    assert manifest["max_possible_physical_attempts"] == 270
    assert manifest["actual_physical_attempts"] == 90
    assert manifest["planned_calls"] == 90
    assert "expected_calls" not in manifest or manifest.get("expected_calls") == 90


def test_summary_reports_operational_metrics_and_no_verdict():
    run = v2.prepare_baseline_run_v2()
    victim = run.cases[0]
    plan_doc = json.loads(victim.raw_response)
    spec = {
        (victim.case_id, 1): [
            _grounding_error_payload(),
            _valid_payload(plan_doc),
        ],
        (victim.case_id, 2): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _valid_payload(plan_doc, _scores(2)),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)
    summary = v2.build_summary_v2(run, v2.aggregate_v0_2(run))

    assert summary["protocol_version"] == "v0.2"
    assert summary["protocol_status"] == "Frozen"
    assert summary["verdict"] is None
    assert "PASS/FAIL threshold" in summary["verdict_note"]
    assert summary["evaluator_retry_enabled"] is False
    assert summary["baseline_attempt_retry_enabled"] is True

    ops = summary["operational_attempt_metrics"]
    assert ops["planned_semantic_repeats"] == 90
    assert ops["successful_semantic_repeats"] == 90
    assert ops["failed_semantic_repeats"] == 0
    assert ops["total_physical_attempts"] == 93
    assert ops["successful_first_attempts"] == 88
    assert ops["successful_after_retry"] == 2
    assert ops["exhausted_after_max_attempts"] == 0
    assert ops["retryable_first_attempt_failures"] == 2
    assert ops["retry_recovery_rate"] == 1.0
    assert ops["attempt_failure_taxonomy_counts"] == {
        "evidence_grounding_error": 3
    }
    assert ops["actual_physical_attempts"] == 93
    assert ops["max_possible_physical_attempts"] == 270


def test_artifacts_are_written_with_retry_columns_and_no_secrets(tmp_path):
    run = v2.prepare_baseline_run_v2()
    victim = run.cases[0]
    plan_doc = json.loads(victim.raw_response)
    spec = {
        (victim.case_id, 1): [
            _grounding_error_payload(),
            _valid_payload(plan_doc),
        ],
        (victim.case_id, 2): [
            _grounding_error_payload(),
            _grounding_error_payload(),
            _grounding_error_payload(),
        ],
        (victim.case_id, 3): [
            _parse_error_payload(),
            _valid_payload(plan_doc),
        ],
    }
    judge = ScriptedJudge(_flat_responses(run.cases, spec))
    v2.execute_baseline_run_v2(run, judge)
    out = tmp_path / "run"
    v2.write_artifacts_v2(run, out, agg=v2.aggregate_v0_2(run))

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

    with (out / "case_metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    row = next(r for r in rows if r["case_id"] == victim.case_id)
    assert row["total_physical_attempts"] == "7"
    assert row["recovered_by_retry_count"] == "2"
    assert row["exhausted_repeat_count"] == "1"
    assert row["first_attempt_successes"] == "0"
    assert row["attempt_failure_types"] == (
        "evidence_grounding_error|judge_response_parse_error"
    )
    assert row["successful_semantic_repeats"] == "2"
    assert row["eligible"] == "True"

    with (out / "block_metrics.csv").open(encoding="utf-8") as handle:
        block_rows = list(csv.DictReader(handle))
    assert [r["block"] for r in block_rows] == ["A", "B", "C"]
    assert [r["n_total"] for r in block_rows] == ["12", "12", "6"]

    with (out / "intent_metrics.csv").open(encoding="utf-8") as handle:
        intent_rows = list(csv.DictReader(handle))
    assert sum(int(r["n_eligible"]) for r in intent_rows) == 30

    blob = "".join(
        p.read_text(encoding="utf-8")
        for p in out.iterdir()
        if p.suffix in (".json", ".csv", ".md", ".jsonl")
    )
    assert "OPENROUTER_API_KEY" not in blob
    assert "api_key" not in blob


def test_dry_run_artifacts_have_no_metrics(tmp_path):
    run = v2.prepare_baseline_run_v2()
    out = tmp_path / "dry"
    v2.write_artifacts_v2(run, out, agg=None)
    assert (out / "run_manifest.json").is_file()
    assert (out / "summary.json").is_file()
    assert (out / "README.md").is_file()
    assert not (out / "evaluations.jsonl").exists()
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["metrics"] is None
    assert summary["protocol_version"] == "v0.2"
    assert summary["operational_attempt_metrics"] is None


def test_prepare_rejects_repeats_other_than_three():
    with pytest.raises(ValueError, match="repeats must be exactly 3"):
        v2.prepare_baseline_run_v2(repeats=2)
    with pytest.raises(ValueError, match="repeats must be exactly 3"):
        v2.prepare_baseline_run_v2(repeats=5)
