"""Tests for the evaluator Pydantic contract models.

Validates frozen constraints: exactly six dimensions, integer-only scores
(0-4), unknown-field rejection, duplicate-flag rejection, multi-flag
acceptance, EvaluationRunContext / JudgeConfig validation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teachintent.evaluator import (
    CRITICAL_FLAGS,
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    JUDGE_PROMPT_VERSION,
    compute_judge_prompt_sha256,
    CriticalFlagResult,
    DiagnosticProbe,
    DiagnosticProbeArtifact,
    DimensionJudgment,
    EvaluatorFailureArtifact,
    EvidenceItem,
    EvaluationRunContext,
    GateFailure,
    JudgeConfig,
    JudgeOutput,
    RunMetadata,
    UniversalEvaluationArtifact,
)

SHA = compute_judge_prompt_sha256()

VALID_EVIDENCE = {"source": "plan.delivery_plan", "text": "{}"}
VALID_DIM = {"score": 4, "evidence": [VALID_EVIDENCE], "brief_justification": "ok"}


def _valid_judge_output_dict():
    return {
        "scores": {d: dict(VALID_DIM) for d in DIMENSION_IDS},
        "critical_flags": [],
    }


# ---------------------------------------------------------------------------
# Exactly six dimensions.
# ---------------------------------------------------------------------------


def test_exactly_six_dimensions():
    assert len(DIMENSION_IDS) == 6
    assert DIMENSION_IDS == (
        "pedagogical_intent_fidelity",
        "content_faithfulness_boundary",
        "learner_state_compatibility",
        "intent_specific_instructional_adequacy",
        "delivery_necessity_sparsity",
        "delivery_pedagogy_alignment",
    )


def test_exactly_seven_critical_flags():
    assert len(CRITICAL_FLAGS) == 7
    assert set(CRITICAL_FLAGS) == {
        "prompt_injection_compliance",
        "false_content_affirmation",
        "content_anchor_contradiction",
        "material_off_anchor_content",
        "learner_humiliation",
        "negative_self_label_reinforcement",
        "coercive_or_hostile_delivery",
    }


# ---------------------------------------------------------------------------
# Score validation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [0, 1, 2, 3, 4])
def test_score_accepts_valid_integers(score):
    dim = DimensionJudgment(score=score, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")
    assert dim.score == score


@pytest.mark.parametrize("bad", [5, -1, 100, -100])
def test_score_rejects_out_of_range(bad):
    with pytest.raises(ValidationError):
        DimensionJudgment(score=bad, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")


@pytest.mark.parametrize("bad", [3.0, 3.5, 4.0])
def test_score_rejects_float(bad):
    with pytest.raises(ValidationError):
        DimensionJudgment(score=bad, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")


@pytest.mark.parametrize("bad", ["3", "4", "good", True, False])
def test_score_rejects_string_and_bool(bad):
    with pytest.raises(ValidationError):
        DimensionJudgment(score=bad, evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")


# ---------------------------------------------------------------------------
# Unknown fields rejected.
# ---------------------------------------------------------------------------


def test_dimension_judgment_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DimensionJudgment(
            score=3,
            evidence=[EvidenceItem(**VALID_EVIDENCE)],
            brief_justification="x",
            extra_field="bad",
        )


def test_evidence_item_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EvidenceItem(source="plan.delivery_plan", text="{}", extra="bad")


def test_judge_output_rejects_unknown_top_level_fields():
    data = _valid_judge_output_dict()
    data["overall_score"] = 50.0
    with pytest.raises(ValidationError):
        JudgeOutput.model_validate(data)


def test_critical_flag_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        CriticalFlagResult(
            flag="learner_humiliation",
            evidence=[EvidenceItem(**VALID_EVIDENCE)],
            brief_justification="x",
            extra="bad",
        )


def test_universal_artifact_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        UniversalEvaluationArtifact(
            evaluator_version="v0.1",
            structural_valid=True,
            gate_failure=None,
            scores={d: VALID_DIM for d in DIMENSION_IDS},
            critical_flags=[],
            overall_score=100.0,
            run_metadata=_valid_run_metadata(),
            extra="bad",
        )


# ---------------------------------------------------------------------------
# Duplicate critical flags rejected; multiple different accepted.
# ---------------------------------------------------------------------------


def test_duplicate_critical_flags_rejected():
    data = _valid_judge_output_dict()
    flag = {
        "flag": "content_anchor_contradiction",
        "evidence": [VALID_EVIDENCE],
        "brief_justification": "x",
    }
    data["critical_flags"] = [dict(flag), dict(flag)]
    with pytest.raises(ValidationError, match="duplicate"):
        JudgeOutput.model_validate(data)


def test_multiple_different_critical_flags_accepted():
    data = _valid_judge_output_dict()
    data["critical_flags"] = [
        {"flag": "content_anchor_contradiction", "evidence": [VALID_EVIDENCE], "brief_justification": "a"},
        {"flag": "learner_humiliation", "evidence": [VALID_EVIDENCE], "brief_justification": "b"},
    ]
    out = JudgeOutput.model_validate(data)
    assert len(out.critical_flags) == 2


def test_critical_flag_rejects_invalid_flag_name():
    with pytest.raises(ValidationError):
        CriticalFlagResult(flag="not_a_real_flag", evidence=[EvidenceItem(**VALID_EVIDENCE)], brief_justification="x")


# ---------------------------------------------------------------------------
# EvaluationRunContext validation.
# ---------------------------------------------------------------------------


def test_run_context_valid():
    ctx = EvaluationRunContext(input_case_id="C-01", generator_version="v0.1", prompt_version="v0.1")
    assert ctx.input_case_id == "C-01"


def test_run_context_rejects_empty_strings():
    with pytest.raises(ValidationError):
        EvaluationRunContext(input_case_id="", generator_version="v0.1", prompt_version="v0.1")


def test_run_context_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EvaluationRunContext(input_case_id="C-01", generator_version="v0.1", prompt_version="v0.1", extra="bad")


# ---------------------------------------------------------------------------
# JudgeConfig validation.
# ---------------------------------------------------------------------------


def _valid_judge_config_dict():
    return {
        "judge_provider": "openrouter",
        "judge_model_requested": "tencent/hy3",
        "temperature": 0,
        "judge_prompt_version": "v0.1",
        "judge_prompt_sha256": SHA,
        "structured_output_enabled": False,
        "retry_enabled": False,
        "self_repair_enabled": False,
    }


def test_judge_config_valid():
    cfg = JudgeConfig.model_validate(_valid_judge_config_dict())
    assert cfg.judge_prompt_version == "v0.1"


def test_judge_config_rejects_wrong_prompt_version():
    data = _valid_judge_config_dict()
    data["judge_prompt_version"] = "v0.2"
    with pytest.raises(ValidationError):
        JudgeConfig.model_validate(data)


def test_judge_config_rejects_bad_sha256():
    data = _valid_judge_config_dict()
    data["judge_prompt_sha256"] = "abc123"
    with pytest.raises(ValidationError):
        JudgeConfig.model_validate(data)


def test_judge_config_rejects_uppercase_sha256():
    data = _valid_judge_config_dict()
    data["judge_prompt_sha256"] = SHA.upper()
    with pytest.raises(ValidationError):
        JudgeConfig.model_validate(data)


def test_judge_config_rejects_negative_temperature():
    data = _valid_judge_config_dict()
    data["temperature"] = -1
    with pytest.raises(ValidationError):
        JudgeConfig.model_validate(data)


def test_judge_config_rejects_unknown_fields():
    data = _valid_judge_config_dict()
    data["extra"] = "bad"
    with pytest.raises(ValidationError):
        JudgeConfig.model_validate(data)


# ---------------------------------------------------------------------------
# RunMetadata / timestamp validation.
# ---------------------------------------------------------------------------


def _valid_run_metadata():
    return RunMetadata(
        judge_provider="openrouter",
        judge_model_requested="tencent/hy3",
        judge_model_reported="tencent/hy3-r",
        temperature=0,
        timestamp="2026-08-28T03:00:00Z",
        input_case_id="C-01",
        generator_version="v0.1",
        prompt_version="v0.1",
        judge_prompt_version="v0.1",
        judge_prompt_sha256=SHA,
        structured_output_enabled=False,
        retry_enabled=False,
        self_repair_enabled=False,
    )


def test_run_metadata_timestamp_must_end_with_Z():
    rm = _valid_run_metadata()
    assert rm.timestamp.endswith("Z")
    data = rm.model_dump()
    data["timestamp"] = "2026-08-28T03:00:00+00:00"
    with pytest.raises(ValidationError):
        RunMetadata.model_validate(data)


def test_run_metadata_rejects_unknown_fields():
    data = _valid_run_metadata().model_dump()
    data["extra"] = "bad"
    with pytest.raises(ValidationError):
        RunMetadata.model_validate(data)


# ---------------------------------------------------------------------------
# GateFailure.
# ---------------------------------------------------------------------------


def test_gate_failure_valid():
    gf = GateFailure(stage="response_parse", summary="bad json")
    assert gf.stage == "response_parse"


def test_gate_failure_rejects_invalid_stage():
    with pytest.raises(ValidationError):
        GateFailure(stage="bad_stage", summary="x")


def test_gate_failure_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        GateFailure(stage="response_parse", summary="x", extra="bad")


# ---------------------------------------------------------------------------
# UniversalEvaluationArtifact state constraints.
# ---------------------------------------------------------------------------


def test_artifact_structural_valid_state():
    artifact = UniversalEvaluationArtifact(
        evaluator_version="v0.1",
        structural_valid=True,
        gate_failure=None,
        scores={d: VALID_DIM for d in DIMENSION_IDS},
        critical_flags=[],
        overall_score=100.0,
        run_metadata=_valid_run_metadata(),
    )
    assert artifact.structural_valid is True


def test_artifact_structural_invalid_state():
    artifact = UniversalEvaluationArtifact(
        evaluator_version="v0.1",
        structural_valid=False,
        gate_failure=GateFailure(stage="response_parse", summary="bad"),
        scores=None,
        critical_flags=[],
        overall_score=None,
        run_metadata=_valid_run_metadata(),
    )
    assert artifact.structural_valid is False
    assert artifact.scores is None


def test_artifact_invalid_valid_true_with_gate_failure():
    with pytest.raises(ValidationError):
        UniversalEvaluationArtifact(
            evaluator_version="v0.1",
            structural_valid=True,
            gate_failure=GateFailure(stage="response_parse", summary="bad"),
            scores={d: VALID_DIM for d in DIMENSION_IDS},
            critical_flags=[],
            overall_score=100.0,
            run_metadata=_valid_run_metadata(),
        )


def test_artifact_invalid_false_without_gate_failure():
    with pytest.raises(ValidationError):
        UniversalEvaluationArtifact(
            evaluator_version="v0.1",
            structural_valid=False,
            gate_failure=None,
            scores=None,
            critical_flags=[],
            overall_score=None,
            run_metadata=_valid_run_metadata(),
        )


# ---------------------------------------------------------------------------
# EvaluatorFailureArtifact.
# ---------------------------------------------------------------------------


def test_failure_artifact_valid():
    fa = EvaluatorFailureArtifact(
        evaluator_version="v0.1",
        input_case_id="C-01",
        failure_type="judge_output_schema_error",
        summary="missing dimension",
        run_metadata=_valid_run_metadata(),
    )
    assert fa.failure_type == "judge_output_schema_error"


def test_failure_artifact_rejects_invalid_failure_type():
    with pytest.raises(ValidationError):
        EvaluatorFailureArtifact(
            evaluator_version="v0.1",
            input_case_id="C-01",
            failure_type="not_a_real_type",
            summary="x",
            run_metadata=None,
        )


def test_failure_artifact_run_metadata_may_be_null():
    fa = EvaluatorFailureArtifact(
        evaluator_version="v0.1",
        input_case_id="C-01",
        failure_type="setup_run_context_error",
        summary="bad context",
        run_metadata=None,
    )
    assert fa.run_metadata is None


def test_failure_artifact_input_case_id_may_be_null_for_run_context_error():
    fa = EvaluatorFailureArtifact(
        evaluator_version="v0.1",
        input_case_id=None,
        failure_type="setup_run_context_error",
        summary="bad context",
        run_metadata=None,
    )
    assert fa.input_case_id is None


# ---------------------------------------------------------------------------
# DiagnosticProbe + DiagnosticProbeArtifact.
# ---------------------------------------------------------------------------


def test_diagnostic_probe_valid():
    dp = DiagnosticProbe(name="must_not_reveal_answer", status="pass")
    assert dp.status == "pass"


def test_diagnostic_probe_rejects_invalid_status():
    with pytest.raises(ValidationError):
        DiagnosticProbe(name="x", status="maybe")


def test_diagnostic_probe_artifact_valid():
    dpa = DiagnosticProbeArtifact(
        evaluator_version="v0.1",
        input_case_id="C-01",
        diagnostic_probes=[DiagnosticProbe(name="x", status="pass")],
    )
    assert len(dpa.diagnostic_probes) == 1


def test_diagnostic_probe_artifact_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DiagnosticProbeArtifact(
            evaluator_version="v0.1",
            input_case_id="C-01",
            diagnostic_probes=[],
            extra="bad",
        )
