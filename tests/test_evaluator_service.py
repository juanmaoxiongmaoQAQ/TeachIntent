"""Tests for the evaluator service: full pipeline integration.

All tests use mocked judge clients -- no real API calls. Covers:
- Layer 0 response_parse / json_schema / pydantic failures
- structural invalid does not call judge
- Layer 1 payload sanitation
- design_expectations / delivery_need not entering judge
- judge raw JSON parsing (via service)
- JudgeOutput schema failure
- evidence validation failure
- deterministic overall score
- Layer 0 failure preserves configured judge metadata
- UTC timestamp ends with Z
- no retry/self-repair unless explicitly configured
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from teachintent.evaluator import (
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    JudgeCompletion,
    JudgeConfig,
    EvaluationRunContext,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
    sanitize_for_judge,
)
from teachintent.evaluator.errors import JudgeAPIError

SHA = compute_judge_prompt_sha256()

INPUT_DOC = {
    "schema_version": "1.0.0-rc.2",
    "output_language": "zh-CN",
    "instructional_content": {
        "subject": "physics",
        "topic": "speed_and_acceleration",
        "content_anchor": "速度表示物体运动的快慢。加速度表示速度随时间变化的快慢。速度大不意味着加速度一定大。",
    },
    "pedagogical_context": {
        "scenario": "The learner has just answered a conceptual question.",
        "learner_utterance": "速度越大，加速度一定越大。",
    },
    "learner": {
        "level": "middle_school",
        "knowledge_state": "misconception",
        "affective_state": "slightly_frustrated",
    },
    "pedagogical_intent": {"primary": "corrective_feedback"},
}

VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {
        "segments": [
            {"segment_id": "seg_01", "text": "你的思路已经很接近了。"},
            {"segment_id": "seg_02", "text": "不过这里有一个关键点需要纠正。"},
        ]
    },
    "delivery_plan": {
        "global": {"attitudinal_tone": "supportive", "emotion": "calm"},
    },
}

DIMS = (
    "pedagogical_intent_fidelity",
    "content_faithfulness_boundary",
    "learner_state_compatibility",
    "intent_specific_instructional_adequacy",
    "delivery_necessity_sparsity",
    "delivery_pedagogy_alignment",
)


def _valid_judge_output_json():
    return json.dumps({
        "scores": {
            d: {
                "score": 4,
                "evidence": [{"source": "plan.delivery_plan", "text": '{"global":{"attitudinal_tone":"supportive","emotion":"calm"}}'}],
                "brief_justification": "ok",
            }
            for d in DIMS
        },
        "critical_flags": [],
    }, ensure_ascii=False)


class FakeJudge:
    """Fake judge backend for testing."""

    def __init__(self, content_fn=None, *, provider="openrouter", model="tencent/hy3", structured_output_enabled=False):
        self._content_fn = content_fn or (lambda idx: _valid_judge_output_json())
        self._provider = provider
        self._model = model
        self._structured_output_enabled = structured_output_enabled
        self.call_count = 0
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
        return self._structured_output_enabled

    def complete(self, system, user, *, temperature=0.0):
        self.call_count += 1
        self.systems.append(system)
        self.users.append(user)
        result = self._content_fn(self.call_count - 1)
        if isinstance(result, Exception):
            raise result
        return JudgeCompletion(
            content=result,
            reported_model="tencent/hy3-reported",
            structured_object=None,
            finish_reason="stop",
        )


def _run_context():
    return EvaluationRunContext(
        input_case_id="PILOT-C-ELI-01",
        generator_version="v0.1",
        prompt_version="v0.1",
    )


def _judge_config(**overrides):
    base = {
        "judge_provider": "openrouter",
        "judge_model_requested": "tencent/hy3",
        "temperature": 0,
        "judge_prompt_version": "v0.1",
        "judge_prompt_sha256": SHA,
        "structured_output_enabled": False,
        "retry_enabled": False,
        "self_repair_enabled": False,
    }
    base.update(overrides)
    return JudgeConfig.model_validate(base)


# ---------------------------------------------------------------------------
# Layer 0: response_parse failure.
# ---------------------------------------------------------------------------


def test_layer0_response_parse_failure():
    judge = FakeJudge()
    result = evaluate_speech_plan(
        INPUT_DOC, "not json at all", _run_context(), _judge_config(), judge
    )
    assert judge.call_count == 0
    assert result.artifact is not None
    assert result.artifact.structural_valid is False
    assert result.artifact.gate_failure.stage == "response_parse"
    assert result.artifact.scores is None
    assert result.artifact.critical_flags == []
    assert result.artifact.overall_score is None


def test_layer0_json_schema_failure():
    judge = FakeJudge()
    # Valid JSON but missing required fields.
    bad_plan = json.dumps({"schema_version": "1.0.0-rc.3"})
    result = evaluate_speech_plan(
        INPUT_DOC, bad_plan, _run_context(), _judge_config(), judge
    )
    assert judge.call_count == 0
    assert result.artifact is not None
    assert result.artifact.structural_valid is False
    assert result.artifact.gate_failure.stage == "json_schema"


def test_layer0_pydantic_failure():
    judge = FakeJudge()
    # Structurally valid JSON that passes JSON Schema but fails Pydantic
    # cross-field validation: a segment_override referencing a non-existent
    # segment_id (Rule 2: segment reference integrity).
    bad_plan = {
        "schema_version": "1.0.0-rc.3",
        "verbal_plan": {
            "segments": [
                {"segment_id": "seg_01", "text": "你的思路已经很接近了。"},
            ]
        },
        "delivery_plan": {
            "segment_overrides": [
                {
                    "segment_id": "seg_99",  # does not exist
                    "prosody": {"speaking_rate": "slow"},
                }
            ]
        },
    }
    bad_plan_json = json.dumps(bad_plan, ensure_ascii=False)
    result = evaluate_speech_plan(
        INPUT_DOC, bad_plan_json, _run_context(), _judge_config(), judge
    )
    assert judge.call_count == 0
    assert result.artifact is not None
    assert result.artifact.structural_valid is False
    assert result.artifact.gate_failure.stage == "pydantic"


# ---------------------------------------------------------------------------
# Structural invalid does not call judge.
# ---------------------------------------------------------------------------


def test_structural_invalid_does_not_call_judge():
    judge = FakeJudge()
    evaluate_speech_plan(
        INPUT_DOC, "", _run_context(), _judge_config(), judge
    )
    assert judge.call_count == 0


# ---------------------------------------------------------------------------
# Layer 1: full success path.
# ---------------------------------------------------------------------------


def test_layer1_full_success():
    judge = FakeJudge()
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(
        INPUT_DOC, raw, _run_context(), _judge_config(), judge
    )
    assert judge.call_count == 1
    assert result.artifact is not None
    assert result.artifact.structural_valid is True
    assert result.artifact.gate_failure is None
    assert result.artifact.scores is not None
    assert set(result.artifact.scores.keys()) == set(DIMS)
    assert result.artifact.overall_score == 100.0
    assert result.artifact.run_metadata.judge_model_reported == "tencent/hy3-reported"


# ---------------------------------------------------------------------------
# Layer 1 payload sanitation.
# ---------------------------------------------------------------------------


def test_layer1_payload_sanitation():
    judge = FakeJudge()
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    user = judge.users[0]
    # Visible input fields must be present.
    assert "output_language" in user
    assert "instructional_content" in user
    assert "pedagogical_context" in user
    assert "pedagogical_intent" in user
    assert "知识_state" not in user  # knowledge_state is under learner, which IS visible
    assert "knowledge_state" in user  # learner is visible
    # schema_version must NOT be in the judge payload.
    assert "1.0.0-rc.2" not in user
    assert "1.0.0-rc.3" not in user


def test_design_expectations_not_in_judge_payload():
    """Even if input had design_expectations (it doesn't), it must not reach judge."""
    judge = FakeJudge()
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    user = judge.users[0]
    assert "design_expectations" not in user
    assert "delivery_need" not in user
    assert "block" not in user.replace("code block", "")  # exclude fence mention
    assert "difficulty" not in user
    assert "PILOT-C-ELI-01" not in user  # input_case_id hidden
    assert "generator_version" not in user


def test_sanitize_function_excludes_hidden_fields():
    input_with_extra = dict(INPUT_DOC)
    # The pilot case wrapper fields are NOT in the input_doc; but verify
    # sanitize picks only visible keys.
    sanitized = sanitize_for_judge(INPUT_DOC, VALID_PLAN)
    assert set(sanitized["input"].keys()) == {
        "output_language", "instructional_content", "pedagogical_context",
        "learner", "pedagogical_intent",
    }
    assert set(sanitized["plan"].keys()) == {"verbal_plan", "delivery_plan"}
    assert "schema_version" not in sanitized["input"]
    assert "schema_version" not in sanitized["plan"]


# ---------------------------------------------------------------------------
# Judge raw JSON parsing (via service, text mode).
# ---------------------------------------------------------------------------


def test_judge_raw_json_parsing_via_service():
    judge = FakeJudge(lambda idx: _valid_judge_output_json())
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact is not None
    assert result.artifact.structural_valid is True


def test_judge_markdown_fence_parsing_via_service():
    body = _valid_judge_output_json()
    fenced = f"```json\n{body}\n```"
    judge = FakeJudge(lambda idx: fenced)
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact is not None
    assert result.artifact.structural_valid is True


# ---------------------------------------------------------------------------
# Malformed judge JSON -> failure.
# ---------------------------------------------------------------------------


def test_malformed_judge_json_produces_failure():
    judge = FakeJudge(lambda idx: '{"bad json')
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "judge_response_parse_error"
    assert result.failure.input_case_id == "PILOT-C-ELI-01"


# ---------------------------------------------------------------------------
# JudgeOutput schema failure.
# ---------------------------------------------------------------------------


def test_judge_output_schema_failure_missing_dimension():
    bad_output = {
        "scores": {d: {"score": 4, "evidence": [{"source": "plan.delivery_plan", "text": '{"global":{"attitudinal_tone":"supportive","emotion":"calm"}}'}], "brief_justification": "ok"} for d in DIMS if d != "delivery_pedagogy_alignment"},
        "critical_flags": [],
    }
    judge = FakeJudge(lambda idx: json.dumps(bad_output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "judge_output_schema_error"


def test_judge_output_schema_failure_extra_top_level():
    bad_output = json.loads(_valid_judge_output_json())
    bad_output["overall_score"] = 50.0
    judge = FakeJudge(lambda idx: json.dumps(bad_output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "judge_output_schema_error"


# ---------------------------------------------------------------------------
# Evidence validation failure.
# ---------------------------------------------------------------------------


def test_evidence_source_error_failure():
    bad_output = json.loads(_valid_judge_output_json())
    bad_output["scores"]["pedagogical_intent_fidelity"]["evidence"] = [
        {"source": "verbal_plan.segments[0].text", "text": "x"}  # invalid path (no root)
    ]
    judge = FakeJudge(lambda idx: json.dumps(bad_output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "evidence_source_error"


def test_evidence_grounding_error_failure():
    bad_output = json.loads(_valid_judge_output_json())
    bad_output["scores"]["pedagogical_intent_fidelity"]["evidence"] = [
        {"source": "input.learner.knowledge_state", "text": "correct_understanding"}  # actual is "misconception"
    ]
    judge = FakeJudge(lambda idx: json.dumps(bad_output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "evidence_grounding_error"


# ---------------------------------------------------------------------------
# Deterministic overall score.
# ---------------------------------------------------------------------------


def test_deterministic_overall_score():
    output = json.loads(_valid_judge_output_json())
    scores = [4, 3, 4, 3, 2, 3]
    for dim, s in zip(DIMS, scores):
        output["scores"][dim]["score"] = s
    judge = FakeJudge(lambda idx: json.dumps(output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact is not None
    # 4+3+4+3+2+3 = 19; 19/24*100 = 79.17
    assert result.artifact.overall_score == 79.17


def test_overall_score_all_zeros():
    output = json.loads(_valid_judge_output_json())
    for dim in DIMS:
        output["scores"][dim]["score"] = 0
    judge = FakeJudge(lambda idx: json.dumps(output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact.overall_score == 0.0


def test_overall_score_all_fours():
    output = json.loads(_valid_judge_output_json())
    for dim in DIMS:
        output["scores"][dim]["score"] = 4
    judge = FakeJudge(lambda idx: json.dumps(output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact.overall_score == 100.0


# ---------------------------------------------------------------------------
# Layer 0 failure preserves configured judge metadata.
# ---------------------------------------------------------------------------


def test_layer0_failure_preserves_judge_metadata():
    judge = FakeJudge()
    result = evaluate_speech_plan(
        INPUT_DOC, "bad json", _run_context(), _judge_config(), judge
    )
    assert result.artifact is not None
    rm = result.artifact.run_metadata
    assert rm.judge_provider == "openrouter"
    assert rm.judge_model_requested == "tencent/hy3"
    assert rm.judge_model_reported is None  # no judge call
    assert rm.temperature == 0
    assert rm.judge_prompt_version == "v0.1"
    assert rm.judge_prompt_sha256 == SHA
    assert rm.structured_output_enabled is False
    assert rm.retry_enabled is False
    assert rm.self_repair_enabled is False
    assert rm.input_case_id == "PILOT-C-ELI-01"


# ---------------------------------------------------------------------------
# UTC timestamp ends with Z.
# ---------------------------------------------------------------------------


def test_timestamp_ends_with_Z():
    judge = FakeJudge()
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact is not None
    assert result.artifact.run_metadata.timestamp.endswith("Z")


def test_timestamp_ends_with_Z_on_layer0_failure():
    judge = FakeJudge()
    result = evaluate_speech_plan(
        INPUT_DOC, "bad", _run_context(), _judge_config(), judge
    )
    assert result.artifact.run_metadata.timestamp.endswith("Z")


# ---------------------------------------------------------------------------
# No retry/self-repair unless explicitly configured.
# ---------------------------------------------------------------------------


def test_single_judge_call_with_retry_disabled():
    judge = FakeJudge()
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert judge.call_count == 1


def test_single_judge_call_even_on_parse_error():
    """Even when judge output is malformed, only one call is made (no retry)."""
    judge = FakeJudge(lambda idx: '{"bad')
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert judge.call_count == 1


def test_single_judge_call_on_schema_error():
    bad_output = {"scores": {}, "critical_flags": []}
    judge = FakeJudge(lambda idx: json.dumps(bad_output))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert judge.call_count == 1


# ---------------------------------------------------------------------------
# Judge API error produces evaluator failure.
# ---------------------------------------------------------------------------


def test_judge_api_error_produces_failure():
    def content_fn(idx):
        raise JudgeAPIError("HTTP 503", status_code=503, response_text="error")
    judge = FakeJudge(content_fn)
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.failure is not None
    assert result.failure.failure_type == "judge_api_error"
    assert judge.call_count == 1


# ---------------------------------------------------------------------------
# Critical flags in judge output.
# ---------------------------------------------------------------------------


def test_judge_output_with_critical_flags():
    output = json.loads(_valid_judge_output_json())
    output["critical_flags"] = [
        {
            "flag": "content_anchor_contradiction",
            "evidence": [{"source": "plan.delivery_plan", "text": '{"global":{"attitudinal_tone":"supportive","emotion":"calm"}}'}],
            "brief_justification": "contradicts anchor",
        }
    ]
    judge = FakeJudge(lambda idx: json.dumps(output, ensure_ascii=False))
    raw = json.dumps(VALID_PLAN, ensure_ascii=False)
    result = evaluate_speech_plan(INPUT_DOC, raw, _run_context(), _judge_config(), judge)
    assert result.artifact is not None
    assert len(result.artifact.critical_flags) == 1
    assert result.artifact.critical_flags[0].flag == "content_anchor_contradiction"
