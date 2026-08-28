"""Regression tests for the TeachIntent Evaluator v0.1 QC fixes.

Each test corresponds to one of the 8 implementation issues fixed in the QC
pass. All tests are offline (no real API calls).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from teachintent.evaluator import (
    DIMENSION_IDS,
    EvaluatorFailureArtifact,
    EvaluationRunContext,
    GateFailure,
    JudgeCompletion,
    JudgeConfig,
    JudgeOutput,
    RunMetadata,
    UniversalEvaluationArtifact,
    compute_judge_prompt_sha256,
    evaluate_speech_plan,
)
from teachintent.evaluator.errors import JudgeAPIError
from teachintent.evaluator.judge import JudgeClient
from teachintent.evaluator.models import (
    EvidenceItem,
    DimensionJudgment,
    CriticalFlagResult,
    _SHA256_RE,
)
from teachintent.evaluator.service import _canonical_utc_now

SHA = compute_judge_prompt_sha256()

DIMS = DIMENSION_IDS

VALID_INPUT = {
    "schema_version": "1.0.0-rc.2",
    "output_language": "zh-CN",
    "instructional_content": {
        "subject": "physics",
        "topic": "speed",
        "content_anchor": "速度大不意味着加速度一定大。",
    },
    "pedagogical_context": {"scenario": "test"},
    "learner": {"level": "middle_school", "knowledge_state": "misconception"},
    "pedagogical_intent": {"primary": "explanation"},
}

VALID_PLAN = {
    "schema_version": "1.0.0-rc.3",
    "verbal_plan": {"segments": [{"segment_id": "seg_01", "text": "测试。"}]},
    "delivery_plan": {},
}

VALID_EVIDENCE = {"source": "plan.delivery_plan", "text": "{}"}


def _valid_judge_output_json():
    return json.dumps({
        "scores": {
            d: {"score": 4, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"}
            for d in DIMS
        },
        "critical_flags": [],
    }, ensure_ascii=False)


class FakeJudge:
    def __init__(self, content_fn=None, *, provider="openrouter", model="tencent/hy3", structured_output_enabled=False):
        self._content_fn = content_fn or (lambda idx: _valid_judge_output_json())
        self._provider = provider
        self._model = model
        self._structured_output_enabled = structured_output_enabled
        self.call_count = 0

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
        result = self._content_fn(self.call_count - 1)
        if isinstance(result, Exception):
            raise result
        return JudgeCompletion(
            content=result,
            reported_model="tencent/hy3-reported",
            structured_object=None,
            finish_reason="stop",
        )


def _ctx_dict():
    return {"input_case_id": "C-01", "generator_version": "v0.1", "prompt_version": "v0.1"}


def _cfg_dict(**ov):
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
    base.update(ov)
    return base


def _valid_run_metadata():
    return RunMetadata(
        judge_provider="openrouter",
        judge_model_requested="tencent/hy3",
        judge_model_reported=None,
        temperature=0,
        timestamp="2026-08-28T06:40:21Z",
        input_case_id="C-01",
        generator_version="v0.1",
        prompt_version="v0.1",
        judge_prompt_version="v0.1",
        judge_prompt_sha256=SHA,
        structured_output_enabled=False,
        retry_enabled=False,
        self_repair_enabled=False,
    )


# ===========================================================================
# Fix #1: UTC timestamp generation + validation
# ===========================================================================


class TestUTCTimestamp:
    def test_canonical_utc_now_format(self):
        ts = _canonical_utc_now()
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), f"bad format: {ts}"

    def test_timestamp_rejects_offset_plus_Z(self):
        with pytest.raises(ValidationError, match="canonical UTC"):
            RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="2026-08-28T06:40:21+00:00Z",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled=False, retry_enabled=False, self_repair_enabled=False,
            )

    def test_timestamp_rejects_offset_without_Z(self):
        with pytest.raises(ValidationError):
            RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="2026-08-28T06:40:21+00:00",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled=False, retry_enabled=False, self_repair_enabled=False,
            )

    def test_timestamp_rejects_just_Z_suffix_invalid_date(self):
        with pytest.raises(ValidationError):
            RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="not-a-dateZ",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled=False, retry_enabled=False, self_repair_enabled=False,
            )

    def test_timestamp_rejects_invalid_calendar_date(self):
        with pytest.raises(ValidationError, match="not a valid UTC"):
            RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="2026-13-45T25:61:61Z",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled=False, retry_enabled=False, self_repair_enabled=False,
            )

    def test_timestamp_accepts_valid_canonical_utc(self):
        rm = _valid_run_metadata()
        assert rm.timestamp == "2026-08-28T06:40:21Z"

    def test_service_generates_canonical_utc_timestamp(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), _cfg_dict(), judge
        )
        assert result.artifact is not None
        ts = result.artifact.run_metadata.timestamp
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts)


# ===========================================================================
# Fix #2: Prompt hash content verification
# ===========================================================================


class TestPromptHashContent:
    def test_wrong_hash_content_rejected_by_service(self):
        """A format-valid 64-hex SHA that doesn't match the frozen prompt hash."""
        wrong_sha = "a" * 64  # 64 lowercase hex, but wrong content
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(judge_prompt_sha256=wrong_sha), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "does not match" in result.failure.summary
        assert judge.call_count == 0

    def test_correct_hash_accepted(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(judge_prompt_sha256=SHA), judge
        )
        assert result.artifact is not None
        assert judge.call_count == 1


# ===========================================================================
# Fix #3: JudgeConfig provenance binding
# ===========================================================================


class TestProvenanceBinding:
    def test_provider_mismatch_rejected(self):
        judge = FakeJudge(provider="different_provider")
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(judge_provider="openrouter"), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "provider mismatch" in result.failure.summary
        assert judge.call_count == 0

    def test_model_mismatch_rejected(self):
        judge = FakeJudge(model="different/model")
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(judge_model_requested="tencent/hy3"), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "model_requested mismatch" in result.failure.summary
        assert judge.call_count == 0

    def test_matching_provider_and_model_accepted(self):
        judge = FakeJudge(provider="openrouter", model="tencent/hy3")
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.artifact is not None
        assert judge.call_count == 1


# ===========================================================================
# Fix #4: Setup validation boundary (dict acceptance + real setup errors)
# ===========================================================================


class TestSetupValidationBoundary:
    def test_dict_run_context_accepted(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.artifact is not None

    def test_dict_judge_config_accepted(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.artifact is not None

    def test_invalid_dict_run_context_produces_setup_error(self):
        """A dict with empty input_case_id triggers setup_run_context_error."""
        judge = FakeJudge()
        bad_ctx = {"input_case_id": "", "generator_version": "v0.1", "prompt_version": "v0.1"}
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            bad_ctx, _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_run_context_error"
        assert result.failure.input_case_id is None
        assert result.failure.run_metadata is None
        assert judge.call_count == 0

    def test_invalid_dict_judge_config_produces_setup_error(self):
        """A dict with wrong prompt version triggers setup_judge_config_error."""
        judge = FakeJudge()
        bad_cfg = _cfg_dict(judge_prompt_version="v0.2")
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), bad_cfg, judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert result.failure.input_case_id == "C-01"
        assert judge.call_count == 0

    def test_setup_run_context_error_with_partial_case_id(self):
        """If run_context dict has a valid input_case_id but invalid other fields,
        the case_id should be recovered."""
        judge = FakeJudge()
        bad_ctx = {"input_case_id": "RECOVERED-01", "generator_version": "", "prompt_version": "v0.1"}
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            bad_ctx, _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_run_context_error"
        assert result.failure.input_case_id == "RECOVERED-01"

    def test_setup_judge_config_preserves_case_id_but_null_metadata(self):
        """setup_judge_config_error has valid case_id but null run_metadata."""
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(judge_prompt_sha256="b" * 64), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert result.failure.input_case_id == "C-01"
        assert result.failure.run_metadata is None


# ===========================================================================
# Fix #5: Reject retry/self-repair config
# ===========================================================================


class TestRejectRetrySelfRepair:
    def test_retry_enabled_true_rejected(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(retry_enabled=True), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "retry" in result.failure.summary.lower()
        assert judge.call_count == 0

    def test_self_repair_enabled_true_rejected(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(self_repair_enabled=True), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "self_repair" in result.failure.summary.lower()
        assert judge.call_count == 0

    def test_both_disabled_accepted(self):
        judge = FakeJudge()
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(retry_enabled=False, self_repair_enabled=False), judge
        )
        assert result.artifact is not None


# ===========================================================================
# Fix #6: Strict frozen contract typing (no silent coercion)
# ===========================================================================


class TestStrictTyping:
    def test_judge_config_rejects_string_bool_structured_output(self):
        with pytest.raises(ValidationError):
            JudgeConfig.model_validate(_cfg_dict(structured_output_enabled="false"))

    def test_judge_config_rejects_int_bool_retry(self):
        with pytest.raises(ValidationError):
            JudgeConfig.model_validate(_cfg_dict(retry_enabled=1))

    def test_judge_config_rejects_string_temperature(self):
        with pytest.raises(ValidationError):
            JudgeConfig.model_validate(_cfg_dict(temperature="0"))

    def test_judge_config_accepts_int_temperature(self):
        cfg = JudgeConfig.model_validate(_cfg_dict(temperature=0))
        assert cfg.temperature == 0.0  # int accepted, stored as float

    def test_judge_config_accepts_float_temperature(self):
        cfg = JudgeConfig.model_validate(_cfg_dict(temperature=0.0))
        assert cfg.temperature == 0.0

    def test_run_context_rejects_int_string_field(self):
        with pytest.raises(ValidationError):
            EvaluationRunContext.model_validate({
                "input_case_id": 123,
                "generator_version": "v0.1",
                "prompt_version": "v0.1",
            })

    def test_evidence_item_rejects_int_source(self):
        with pytest.raises(ValidationError):
            EvidenceItem(source=123, text="x")

    def test_dimension_judgment_rejects_string_score(self):
        with pytest.raises(ValidationError):
            DimensionJudgment(score="3", evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")

    def test_dimension_judgment_rejects_bool_score(self):
        with pytest.raises(ValidationError):
            DimensionJudgment(score=True, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")

    def test_dimension_judgment_rejects_float_score(self):
        with pytest.raises(ValidationError):
            DimensionJudgment(score=3.0, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")

    def test_gate_failure_rejects_int_summary(self):
        with pytest.raises(ValidationError):
            GateFailure(stage="response_parse", summary=123)

    def test_run_metadata_rejects_string_bool(self):
        with pytest.raises(ValidationError):
            RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="2026-08-28T06:40:21Z",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled="false",
                retry_enabled=False, self_repair_enabled=False,
            )

    def test_universal_artifact_rejects_int_bool_structural_valid(self):
        with pytest.raises(ValidationError):
            UniversalEvaluationArtifact(
                evaluator_version="v0.1",
                structural_valid=1,  # int, not bool
                gate_failure=None,
                scores=None,
                critical_flags=[],
                overall_score=None,
                run_metadata=_valid_run_metadata(),
            )


# ===========================================================================
# Fix #7: Strengthen artifact model invariants
# ===========================================================================


class TestArtifactInvariants:
    def test_failure_artifact_rejects_null_case_id_for_non_run_context_error(self):
        with pytest.raises(ValidationError, match="input_case_id may be null only"):
            EvaluatorFailureArtifact(
                evaluator_version="v0.1",
                input_case_id=None,
                failure_type="judge_api_error",
                summary="x",
                run_metadata=_valid_run_metadata(),
            )

    def test_failure_artifact_rejects_null_metadata_for_post_setup_failure(self):
        with pytest.raises(ValidationError, match="run_metadata may be null only"):
            EvaluatorFailureArtifact(
                evaluator_version="v0.1",
                input_case_id="C-01",
                failure_type="evidence_source_error",
                summary="x",
                run_metadata=None,
            )

    def test_failure_artifact_requires_metadata_for_judge_api_error(self):
        with pytest.raises(ValidationError, match="run_metadata may be null only"):
            EvaluatorFailureArtifact(
                evaluator_version="v0.1",
                input_case_id="C-01",
                failure_type="judge_api_error",
                summary="x",
                run_metadata=None,
            )

    def test_artifact_rejects_inconsistent_overall_score(self):
        """overall_score must match round(sum/24*100, 2)."""
        scores = {d: {"score": 4, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"} for d in DIMS}
        with pytest.raises(ValidationError, match="inconsistent"):
            UniversalEvaluationArtifact(
                evaluator_version="v0.1",
                structural_valid=True,
                gate_failure=None,
                scores=scores,
                critical_flags=[],
                overall_score=50.0,  # should be 100.0
                run_metadata=_valid_run_metadata(),
            )

    def test_artifact_rejects_duplicate_critical_flags_on_direct_construction(self):
        scores = {d: {"score": 4, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"} for d in DIMS}
        flag = {
            "flag": "content_anchor_contradiction",
            "evidence": [VALID_EVIDENCE],
            "brief_justification": "x",
        }
        with pytest.raises(ValidationError, match="duplicate critical flag"):
            UniversalEvaluationArtifact(
                evaluator_version="v0.1",
                structural_valid=True,
                gate_failure=None,
                scores=scores,
                critical_flags=[dict(flag), dict(flag)],
                overall_score=100.0,
                run_metadata=_valid_run_metadata(),
            )

    def test_artifact_accepts_consistent_overall_score(self):
        scores = {d: {"score": 3, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"} for d in DIMS}
        # 3*6=18, 18/24*100=75.0
        artifact = UniversalEvaluationArtifact(
            evaluator_version="v0.1",
            structural_valid=True,
            gate_failure=None,
            scores=scores,
            critical_flags=[],
            overall_score=75.0,
            run_metadata=_valid_run_metadata(),
        )
        assert artifact.overall_score == 75.0


# ===========================================================================
# Fix #8: Post-judge provenance + malformed payload taxonomy
# ===========================================================================


class TestPostJudgeProvenanceAndMalformedPayload:
    def test_judge_output_schema_error_preserves_reported_model(self):
        """When judge output fails schema validation, reported_model must be preserved."""
        bad_output = {"scores": {}, "critical_flags": []}
        judge = FakeJudge(lambda idx: json.dumps(bad_output))
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "judge_output_schema_error"
        assert result.failure.run_metadata is not None
        assert result.failure.run_metadata.judge_model_reported == "tencent/hy3-reported"

    def test_evidence_source_error_preserves_reported_model(self):
        bad_output = json.loads(_valid_judge_output_json())
        bad_output["scores"]["pedagogical_intent_fidelity"]["evidence"] = [
            {"source": "no_root.segments[0].text", "text": "x"}
        ]
        judge = FakeJudge(lambda idx: json.dumps(bad_output))
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "evidence_source_error"
        assert result.failure.run_metadata is not None
        assert result.failure.run_metadata.judge_model_reported == "tencent/hy3-reported"

    def test_evidence_grounding_error_preserves_reported_model(self):
        bad_output = json.loads(_valid_judge_output_json())
        bad_output["scores"]["pedagogical_intent_fidelity"]["evidence"] = [
            {"source": "input.learner.knowledge_state", "text": "wrong_value"}
        ]
        judge = FakeJudge(lambda idx: json.dumps(bad_output))
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "evidence_grounding_error"
        assert result.failure.run_metadata.judge_model_reported == "tencent/hy3-reported"

    def test_judge_response_parse_error_preserves_reported_model(self):
        """When judge text is malformed JSON, reported_model is still preserved."""
        judge = FakeJudge(lambda idx: '{"bad json')
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "judge_response_parse_error"
        assert result.failure.run_metadata.judge_model_reported == "tencent/hy3-reported"

    def test_judge_api_error_does_not_preserve_reported_model(self):
        """When the API call itself fails, there is no completion, so reported_model=None."""
        def content_fn(idx):
            raise JudgeAPIError("HTTP 503", status_code=503, response_text="err")
        judge = FakeJudge(content_fn)
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "judge_api_error"
        assert result.failure.run_metadata.judge_model_reported is None

    def test_malformed_provider_payload_is_judge_api_error(self):
        """JudgeClient with malformed choices structure raises JudgeAPIError, not parse error."""
        import httpx
        # Build a mock transport that returns a response with no choices array.
        def mock_handler(request):
            return httpx.Response(
                200,
                json={"id": "x", "model": "m"},
            )
        transport = httpx.MockTransport(mock_handler)
        client = JudgeClient(
            api_key="fake",
            base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3",
            provider="openrouter",
            transport=transport,
        )
        with pytest.raises(JudgeAPIError, match="choices"):
            client.complete("sys", "usr")

    def test_malformed_message_content_is_judge_api_error(self):
        """JudgeClient with missing content raises JudgeAPIError."""
        import httpx
        def mock_handler(request):
            return httpx.Response(
                200,
                json={
                    "model": "m",
                    "choices": [{"message": {}, "finish_reason": "stop"}],
                },
            )
        transport = httpx.MockTransport(mock_handler)
        client = JudgeClient(
            api_key="fake",
            base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3",
            provider="openrouter",
            transport=transport,
        )
        with pytest.raises(JudgeAPIError, match="content"):
            client.complete("sys", "usr")

    def test_malformed_reported_model_type_is_judge_api_error(self):
        """JudgeClient with non-string reported model raises JudgeAPIError."""
        import httpx
        def mock_handler(request):
            return httpx.Response(
                200,
                json={
                    "model": 12345,  # not a string
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )
        transport = httpx.MockTransport(mock_handler)
        client = JudgeClient(
            api_key="fake",
            base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3",
            provider="openrouter",
            transport=transport,
        )
        with pytest.raises(JudgeAPIError, match="model.*not a string"):
            client.complete("sys", "usr")


# ===========================================================================
# Final regression round: 4 remaining issues.
# ===========================================================================


# ===========================================================================
# Fix #1 (final): service boundary re-validates pre-constructed models.
# ===========================================================================


class TestBoundaryRevalidation:
    def test_run_context_model_construct_with_invalid_fields(self):
        """model_construct() bypasses validation; service must re-validate."""
        judge = FakeJudge()
        # model_construct skips all validators, so empty strings are accepted.
        bad_ctx = EvaluationRunContext.model_construct(
            input_case_id="", generator_version="", prompt_version=""
        )
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), bad_ctx, _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_run_context_error"
        assert judge.call_count == 0

    def test_run_context_model_construct_with_wrong_type(self):
        """model_construct with non-string input_case_id must be re-validated."""
        judge = FakeJudge()
        bad_ctx = EvaluationRunContext.model_construct(
            input_case_id=123, generator_version="v0.1", prompt_version="v0.1"
        )
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), bad_ctx, _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_run_context_error"
        assert judge.call_count == 0

    def test_judge_config_model_construct_with_invalid_fields(self):
        """JudgeConfig.model_construct() with invalid fields must be re-validated."""
        judge = FakeJudge()
        bad_cfg = JudgeConfig.model_construct(
            judge_provider="openrouter",
            judge_model_requested="tencent/hy3",
            temperature=0,
            judge_prompt_version="v0.1",
            judge_prompt_sha256="not-a-valid-hash",  # invalid
            structured_output_enabled=False,
            retry_enabled=False,
            self_repair_enabled=False,
        )
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), bad_cfg, judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert judge.call_count == 0

    def test_judge_config_model_construct_with_wrong_structured_output_type(self):
        """model_construct with string structured_output_enabled must fail."""
        judge = FakeJudge()
        bad_cfg = JudgeConfig.model_construct(
            judge_provider="openrouter",
            judge_model_requested="tencent/hy3",
            temperature=0,
            judge_prompt_version="v0.1",
            judge_prompt_sha256=SHA,
            structured_output_enabled="false",  # string, not bool
            retry_enabled=False,
            self_repair_enabled=False,
        )
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), bad_cfg, judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert judge.call_count == 0

    def test_valid_model_instance_still_passes(self):
        """A correctly constructed model still passes (re-validation is transparent)."""
        judge = FakeJudge()
        ctx = EvaluationRunContext(input_case_id="C-01", generator_version="v0.1", prompt_version="v0.1")
        cfg = JudgeConfig.model_validate(_cfg_dict())
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), ctx, cfg, judge
        )
        assert result.artifact is not None
        assert judge.call_count == 1


# ===========================================================================
# Fix #2 (final): structured_output provenance binding.
# ===========================================================================


class TestStructuredOutputProvenanceBinding:
    def test_config_false_backend_true_rejected(self):
        """config structured_output_enabled=False, backend=True -> setup error."""
        judge = FakeJudge(structured_output_enabled=True)
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(structured_output_enabled=False), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "structured_output_enabled mismatch" in result.failure.summary
        assert judge.call_count == 0

    def test_config_true_backend_false_rejected(self):
        """config structured_output_enabled=True, backend=False -> setup error."""
        judge = FakeJudge(structured_output_enabled=False)
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(structured_output_enabled=True), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "setup_judge_config_error"
        assert "structured_output_enabled mismatch" in result.failure.summary
        assert judge.call_count == 0

    def test_matching_structured_output_accepted(self):
        """config=False + backend=False passes."""
        judge = FakeJudge(structured_output_enabled=False)
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN),
            _ctx_dict(), _cfg_dict(structured_output_enabled=False), judge
        )
        assert result.artifact is not None
        assert judge.call_count == 1

    def test_judge_client_structured_output_property(self):
        """JudgeClient.structured_output_enabled reflects response_format."""
        import httpx
        client = JudgeClient(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3", provider="openrouter", response_format=None,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={})),
        )
        assert client.structured_output_enabled is False
        client2 = JudgeClient(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3", provider="openrouter",
            response_format={"type": "json_object"},
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={})),
        )
        assert client2.structured_output_enabled is True


# ===========================================================================
# Fix #3 (final): malformed provider payload taxonomy (top-level + reported model).
# ===========================================================================


class TestMalformedPayloadTopLevel:
    def _client(self, response_body):
        import httpx
        def handler(request):
            return httpx.Response(200, json=response_body)
        return JudgeClient(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3", provider="openrouter",
            transport=httpx.MockTransport(handler),
        )

    def test_top_level_list_rejected(self):
        client = self._client([])
        with pytest.raises(JudgeAPIError, match="top-level is not an object"):
            client.complete("sys", "usr")

    def test_top_level_string_rejected(self):
        client = self._client("hello")
        with pytest.raises(JudgeAPIError, match="top-level is not an object"):
            client.complete("sys", "usr")

    def test_top_level_number_rejected(self):
        client = self._client(123)
        with pytest.raises(JudgeAPIError, match="top-level is not an object"):
            client.complete("sys", "usr")

    def test_top_level_null_rejected(self):
        import httpx
        def handler(request):
            return httpx.Response(200, content=b"null", headers={"content-type": "application/json"})
        client = JudgeClient(
            api_key="fake", base_url="https://openrouter.ai/api/v1",
            model="tencent/hy3", provider="openrouter",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(JudgeAPIError, match="top-level is not an object"):
            client.complete("sys", "usr")

    def test_reported_model_empty_string_rejected(self):
        client = self._client({
            "model": "",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        })
        with pytest.raises(JudgeAPIError, match="empty or whitespace"):
            client.complete("sys", "usr")

    def test_reported_model_whitespace_rejected(self):
        client = self._client({
            "model": "   ",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        })
        with pytest.raises(JudgeAPIError, match="empty or whitespace"):
            client.complete("sys", "usr")

    def test_reported_model_int_rejected(self):
        client = self._client({
            "model": 123,
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        })
        with pytest.raises(JudgeAPIError, match="not a string"):
            client.complete("sys", "usr")


# ===========================================================================
# Fix #4 (final): per-run reported_model (no module-level global).
# ===========================================================================


class TestPerRunReportedModel:
    def test_no_module_level_stash_exists(self):
        import teachintent.evaluator.service as service_mod
        assert not hasattr(service_mod, "_last_reported_model")

    def test_interleaved_runs_do_not_cross_contaminate(self):
        """Two runs with different reported_models must not cross-contaminate.

        Run A: judge output schema error, reported_model="model-A".
        Run B: judge output schema error, reported_model="model-B".
        Both failures must carry their OWN reported_model.
        """
        def make_judge(reported_model):
            def content_fn(idx):
                return json.dumps({"scores": {}, "critical_flags": []})  # schema error
            class _J(FakeJudge):
                def complete(self, system, user, *, temperature=0.0):
                    self.call_count += 1
                    result = self._content_fn(self.call_count - 1)
                    if isinstance(result, Exception):
                        raise result
                    return JudgeCompletion(
                        content=result,
                        reported_model=reported_model,
                        structured_object=None,
                        finish_reason="stop",
                    )
            return _J(content_fn)

        judge_a = make_judge("model-A")
        judge_b = make_judge("model-B")

        # Interleave: run A first, then B.
        result_a = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), _cfg_dict(), judge_a
        )
        result_b = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), _cfg_dict(), judge_b
        )

        assert result_a.failure is not None
        assert result_a.failure.failure_type == "judge_output_schema_error"
        assert result_a.failure.run_metadata.judge_model_reported == "model-A"

        assert result_b.failure is not None
        assert result_b.failure.failure_type == "judge_output_schema_error"
        assert result_b.failure.run_metadata.judge_model_reported == "model-B"

        # Re-run A again to confirm it still reports "model-A" (no stale B).
        result_a2 = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), _cfg_dict(), judge_a
        )
        assert result_a2.failure.run_metadata.judge_model_reported == "model-A"

    def test_judge_api_error_reported_model_is_none(self):
        """API failure (no completion) -> reported_model None."""
        def content_fn(idx):
            raise JudgeAPIError("HTTP 503", status_code=503, response_text="err")
        judge = FakeJudge(content_fn)
        result = evaluate_speech_plan(
            VALID_INPUT, json.dumps(VALID_PLAN), _ctx_dict(), _cfg_dict(), judge
        )
        assert result.failure is not None
        assert result.failure.failure_type == "judge_api_error"
        assert result.failure.run_metadata.judge_model_reported is None


# ===========================================================================
# Fix #5 (final): strict overall_score typing.
# ===========================================================================


class TestStrictOverallScore:
    def _artifact_with_overall(self, overall_score):
        scores = {d: {"score": 4, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"} for d in DIMS}
        return UniversalEvaluationArtifact(
            evaluator_version="v0.1",
            structural_valid=True,
            gate_failure=None,
            scores=scores,
            critical_flags=[],
            overall_score=overall_score,
            run_metadata=RunMetadata(
                judge_provider="p", judge_model_requested="m", temperature=0,
                timestamp="2026-08-28T06:40:21Z",
                input_case_id="c", generator_version="v", prompt_version="v",
                judge_prompt_version="v0.1", judge_prompt_sha256=SHA,
                structured_output_enabled=False, retry_enabled=False, self_repair_enabled=False,
            ),
        )

    def test_overall_score_rejects_string(self):
        with pytest.raises(ValidationError):
            self._artifact_with_overall("100.0")

    def test_overall_score_accepts_int(self):
        artifact = self._artifact_with_overall(100)
        assert artifact.overall_score == 100.0

    def test_overall_score_accepts_float(self):
        artifact = self._artifact_with_overall(100.0)
        assert artifact.overall_score == 100.0