"""Pydantic models for the TeachIntent Evaluator v0.1 contracts.

All frozen contract objects reject unknown fields (``extra="forbid"``),
explicit nulls, and silent Pydantic coercion. Score fields are strictly
integers in ``{0, 1, 2, 3, 4}`` -- floats, strings, bools, and out-of-range
values are rejected. Boolean fields reject string/int coercion. String fields
reject int/float coercion.

These models are the evaluator's own contracts; they do NOT duplicate or relax
the Generator's Input/Output contract models. The evaluator reuses the
Generator's canonical validation pipeline for Layer 0 (see ``service.py``).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from .rubric import (
    DIMENSION_IDS,
)

__all__ = [
    "EvaluationRunContext",
    "JudgeConfig",
    "EvidenceItem",
    "DimensionJudgment",
    "CriticalFlagResult",
    "JudgeOutput",
    "GateFailure",
    "RunMetadata",
    "UniversalEvaluationArtifact",
    "EvaluatorFailureArtifact",
    "DiagnosticProbe",
    "DiagnosticProbeArtifact",
]


# ---------------------------------------------------------------------------
# Strict typing helpers — prevent Pydantic silent coercion.
# ---------------------------------------------------------------------------
def _strict_str(v) -> str:
    """Reject non-str values (int, float, bool) before Pydantic coercion."""
    if isinstance(v, bool) or not isinstance(v, str):
        raise ValueError(
            f"expected a string, got {v!r} of type {type(v).__name__}"
        )
    return v


def _strict_bool(v) -> bool:
    """Reject string/int coercion (e.g. 'false'->False, 1->True)."""
    if not isinstance(v, bool):
        raise ValueError(
            f"expected a boolean, got {v!r} of type {type(v).__name__}"
        )
    return v


def _strict_temperature(v) -> float:
    """Accept int or float (JSON number), but reject string/bool."""
    if isinstance(v, bool):
        raise ValueError(f"temperature must be a number, got bool {v!r}")
    if not isinstance(v, (int, float)):
        raise ValueError(
            f"temperature must be a number, got {v!r} of type {type(v).__name__}"
        )
    return float(v)


def _strict_float(v) -> float:
    """Accept int or float (JSON number), reject string/bool coercion."""
    if isinstance(v, bool):
        raise ValueError(f"expected a number, got bool {v!r}")
    if not isinstance(v, (int, float)):
        raise ValueError(
            f"expected a number, got {v!r} of type {type(v).__name__}"
        )
    return float(v)


StrictStr = Annotated[str, BeforeValidator(_strict_str)]
StrictBool = Annotated[bool, BeforeValidator(_strict_bool)]
StrictTemperature = Annotated[float, BeforeValidator(_strict_temperature)]
StrictFloat = Annotated[float, BeforeValidator(_strict_float)]


class _EvaluatorBaseModel(BaseModel):
    """Base for all evaluator contract models: extra fields forbidden, strict
    coercion, explicit null rejection."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Setup: EvaluationRunContext (Section 4.2).
# ---------------------------------------------------------------------------
class EvaluationRunContext(_EvaluatorBaseModel):
    """Provenance metadata for one evaluation run. MUST NOT be shown to Layer 1."""

    input_case_id: StrictStr = Field(..., min_length=1)
    generator_version: StrictStr = Field(..., min_length=1)
    prompt_version: StrictStr = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Setup: JudgeConfig (Section 4.3).
# ---------------------------------------------------------------------------
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class JudgeConfig(_EvaluatorBaseModel):
    """Frozen judge configuration for one evaluation run.

    ``retry_enabled`` and ``self_repair_enabled`` MUST be ``False`` in
    Evaluator v0.1 (the logic is not implemented; accepting ``True`` would
    falsely declare a condition that does not exist). This is enforced at
    the service boundary, not here, so that the model can be constructed for
    inspection before the service rejects it.
    """

    judge_provider: StrictStr = Field(..., min_length=1)
    judge_model_requested: StrictStr = Field(..., min_length=1)
    temperature: StrictTemperature = Field(..., ge=0)
    judge_prompt_version: Literal["v0.1"]
    judge_prompt_sha256: StrictStr
    structured_output_enabled: StrictBool
    retry_enabled: StrictBool
    self_repair_enabled: StrictBool

    @field_validator("judge_prompt_sha256")
    @classmethod
    def _validate_sha256(cls, v: str) -> str:
        if not isinstance(v, str) or _SHA256_RE.match(v) is None:
            raise ValueError(
                "judge_prompt_sha256 must be exactly 64 lowercase hexadecimal "
                f"characters (got {v!r})"
            )
        return v


# ---------------------------------------------------------------------------
# Evidence (Section 17.1).
# ---------------------------------------------------------------------------
class EvidenceItem(_EvaluatorBaseModel):
    """One evidence item: a source path + grounded text."""

    source: StrictStr = Field(..., min_length=1)
    text: StrictStr = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# DimensionJudgment (Section 20).
# ---------------------------------------------------------------------------
def _strict_score_validator(v):
    """Reject bool, float, string, and non-int values before Pydantic coercion."""
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(
            f"score must be an integer in 0-4 (got {v!r} of type {type(v).__name__})"
        )
    if v not in (0, 1, 2, 3, 4):
        raise ValueError(f"score must be one of 0,1,2,3,4 (got {v})")
    return v


StrictScore = Annotated[int, BeforeValidator(_strict_score_validator)]


class DimensionJudgment(_EvaluatorBaseModel):
    """One dimension's score + evidence + justification."""

    score: StrictScore
    evidence: list[EvidenceItem] = Field(..., min_length=1)
    brief_justification: StrictStr = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# CriticalFlagResult (Section 19).
# ---------------------------------------------------------------------------
class CriticalFlagResult(_EvaluatorBaseModel):
    """One raised critical flag with evidence + justification."""

    flag: Literal[
        "prompt_injection_compliance",
        "false_content_affirmation",
        "content_anchor_contradiction",
        "material_off_anchor_content",
        "learner_humiliation",
        "negative_self_label_reinforcement",
        "coercive_or_hostile_delivery",
    ]
    evidence: list[EvidenceItem] = Field(..., min_length=1)
    brief_justification: StrictStr = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# JudgeOutput (Section 21) -- exactly two top-level fields.
# ---------------------------------------------------------------------------
class JudgeOutput(_EvaluatorBaseModel):
    """The Layer 1 LLM judge output contract."""

    scores: dict[str, DimensionJudgment]
    critical_flags: list[CriticalFlagResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_scores_keys(self) -> "JudgeOutput":
        expected = set(DIMENSION_IDS)
        actual = set(self.scores.keys())
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            parts = []
            if missing:
                parts.append(f"missing: {missing}")
            if extra:
                parts.append(f"unexpected: {extra}")
            raise ValueError(
                "scores must contain exactly the six frozen dimension keys; "
                + "; ".join(parts)
            )
        # Duplicate flag types rejected.
        flag_types = [cf.flag for cf in self.critical_flags]
        seen: set[str] = set()
        duplicates: list[str] = []
        for ft in flag_types:
            if ft in seen:
                duplicates.append(ft)
            seen.add(ft)
        if duplicates:
            raise ValueError(
                f"duplicate critical flag type(s): {duplicates}"
            )
        return self


# ---------------------------------------------------------------------------
# GateFailure (Section 24.2).
# ---------------------------------------------------------------------------
class GateFailure(_EvaluatorBaseModel):
    """Layer 0 gate failure: identifies the failed stage."""

    stage: Literal["response_parse", "json_schema", "pydantic"]
    summary: StrictStr = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# RunMetadata (Section 24.1).
# ---------------------------------------------------------------------------
_UTC_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


def _validate_utc_timestamp(v: str) -> str:
    """Validate canonical UTC ISO-8601 ending in Z (no offset).

    Accepts exactly: YYYY-MM-DDTHH:MM:SSZ
    Rejects: offsets like +00:00, +00:00Z, local times, non-ISO strings.
    """
    if not isinstance(v, str):
        raise ValueError(
            f"timestamp must be a string, got {v!r} of type {type(v).__name__}"
        )
    if _UTC_ISO_RE.match(v) is None:
        raise ValueError(
            f"timestamp must be canonical UTC ISO-8601 "
            f"(YYYY-MM-DDTHH:MM:SSZ); got {v!r}"
        )
    # Validate it's a real date/time (not e.g. 2026-13-45T25:61:61Z).
    try:
        datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(
            f"timestamp is not a valid UTC date/time: {v!r} ({exc})"
        ) from exc
    return v


UTC_TIMESTAMP = Annotated[str, BeforeValidator(_validate_utc_timestamp)]


class RunMetadata(_EvaluatorBaseModel):
    """Run-level metadata preserved in every artifact."""

    judge_provider: StrictStr = Field(..., min_length=1)
    judge_model_requested: StrictStr = Field(..., min_length=1)
    judge_model_reported: StrictStr | None = None
    temperature: StrictTemperature = Field(..., ge=0)
    timestamp: UTC_TIMESTAMP
    input_case_id: StrictStr = Field(..., min_length=1)
    generator_version: StrictStr = Field(..., min_length=1)
    prompt_version: StrictStr = Field(..., min_length=1)
    judge_prompt_version: Literal["v0.1"]
    judge_prompt_sha256: StrictStr
    structured_output_enabled: StrictBool
    retry_enabled: StrictBool
    self_repair_enabled: StrictBool

    @field_validator("judge_prompt_sha256")
    @classmethod
    def _validate_sha256(cls, v: str) -> str:
        if not isinstance(v, str) or _SHA256_RE.match(v) is None:
            raise ValueError(
                "judge_prompt_sha256 must be exactly 64 lowercase hexadecimal "
                f"characters (got {v!r})"
            )
        return v

    @field_validator("judge_model_reported")
    @classmethod
    def _validate_reported_model(cls, v):
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError(
                "judge_model_reported must be null or a non-empty string"
            )
        return v


# ---------------------------------------------------------------------------
# UniversalEvaluationArtifact (Section 24).
# ---------------------------------------------------------------------------
class UniversalEvaluationArtifact(_EvaluatorBaseModel):
    """The final universal evaluation artifact."""

    evaluator_version: Literal["v0.1"]
    structural_valid: StrictBool
    gate_failure: GateFailure | None = None
    scores: dict[str, DimensionJudgment] | None = None
    critical_flags: list[CriticalFlagResult] = Field(default_factory=list)
    overall_score: StrictFloat | None = None
    run_metadata: RunMetadata

    @model_validator(mode="after")
    def _validate_state_constraints(self) -> "UniversalEvaluationArtifact":
        if self.structural_valid:
            if self.gate_failure is not None:
                raise ValueError(
                    "structural_valid=true requires gate_failure=null"
                )
            if self.scores is None:
                raise ValueError(
                    "structural_valid=true requires non-null scores"
                )
            if self.overall_score is None:
                raise ValueError(
                    "structural_valid=true requires non-null overall_score"
                )
            # scores must contain exactly the six frozen keys.
            expected = set(DIMENSION_IDS)
            actual = set(self.scores.keys())
            if actual != expected:
                raise ValueError(
                    f"scores keys mismatch: expected {sorted(expected)}, "
                    f"got {sorted(actual)}"
                )
            # overall_score must be consistent with scores (deterministic).
            score_sum = sum(self.scores[d].score for d in DIMENSION_IDS)
            expected_overall = round(score_sum / 24 * 100, 2)
            if self.overall_score != expected_overall:
                raise ValueError(
                    f"overall_score={self.overall_score} inconsistent with "
                    f"scores (expected {expected_overall})"
                )
            # critical_flags: no duplicate flag types.
            flag_types = [cf.flag for cf in self.critical_flags]
            seen: set[str] = set()
            duplicates: list[str] = []
            for ft in flag_types:
                if ft in seen:
                    duplicates.append(ft)
                seen.add(ft)
            if duplicates:
                raise ValueError(
                    f"duplicate critical flag type(s) in artifact: {duplicates}"
                )
        else:
            if self.gate_failure is None:
                raise ValueError(
                    "structural_valid=false requires non-null gate_failure"
                )
            if self.scores is not None:
                raise ValueError(
                    "structural_valid=false requires scores=null"
                )
            if self.overall_score is not None:
                raise ValueError(
                    "structural_valid=false requires overall_score=null"
                )
            if self.critical_flags:
                raise ValueError(
                    "structural_valid=false requires critical_flags=[]"
                )
        return self


# ---------------------------------------------------------------------------
# EvaluatorFailureArtifact (Section 31).
# ---------------------------------------------------------------------------
# Failure types that occur AFTER run context + judge config are validated.
# These MUST carry non-null run_metadata and non-null input_case_id.
_POST_SETUP_FAILURE_TYPES = frozenset({
    "judge_api_error",
    "judge_response_parse_error",
    "judge_output_schema_error",
    "evidence_source_error",
    "evidence_grounding_error",
    "internal_evaluator_error",
})


class EvaluatorFailureArtifact(_EvaluatorBaseModel):
    """Typed evaluator/setup failure artifact."""

    evaluator_version: Literal["v0.1"]
    input_case_id: StrictStr | None = None
    failure_type: Literal[
        "setup_input_jsonschema_error",
        "setup_input_pydantic_error",
        "setup_run_context_error",
        "setup_judge_config_error",
        "judge_api_error",
        "judge_response_parse_error",
        "judge_output_schema_error",
        "evidence_source_error",
        "evidence_grounding_error",
        "internal_evaluator_error",
    ]
    summary: StrictStr = Field(..., min_length=1)
    run_metadata: RunMetadata | None = None

    @model_validator(mode="after")
    def _validate_invariants(self) -> "EvaluatorFailureArtifact":
        # input_case_id == null only allowed for setup_run_context_error.
        if self.input_case_id is None:
            if self.failure_type != "setup_run_context_error":
                raise ValueError(
                    f"input_case_id may be null only for "
                    f"setup_run_context_error, got {self.failure_type}"
                )
        # run_metadata == null only allowed for early setup failures.
        if self.run_metadata is None:
            if self.failure_type not in (
                "setup_run_context_error",
                "setup_judge_config_error",
            ):
                raise ValueError(
                    f"run_metadata may be null only for early setup failures "
                    f"(setup_run_context_error / setup_judge_config_error), "
                    f"got {self.failure_type}"
                )
        # Post-setup failures MUST carry run_metadata.
        if self.failure_type in _POST_SETUP_FAILURE_TYPES:
            if self.run_metadata is None:
                raise ValueError(
                    f"{self.failure_type} requires non-null run_metadata"
                )
            if self.input_case_id is None:
                raise ValueError(
                    f"{self.failure_type} requires non-null input_case_id"
                )
        return self


# ---------------------------------------------------------------------------
# Layer 2: DiagnosticProbe + DiagnosticProbeArtifact (Section 26.1).
# ---------------------------------------------------------------------------
class DiagnosticProbe(_EvaluatorBaseModel):
    """One Layer 2 diagnostic probe result."""

    name: StrictStr = Field(..., min_length=1)
    status: Literal["pass", "fail", "uncertain"]


class DiagnosticProbeArtifact(_EvaluatorBaseModel):
    """Layer 2 diagnostic probe artifact (separate from universal Layer 1)."""

    evaluator_version: Literal["v0.1"]
    input_case_id: StrictStr = Field(..., min_length=1)
    diagnostic_probes: list[DiagnosticProbe]
