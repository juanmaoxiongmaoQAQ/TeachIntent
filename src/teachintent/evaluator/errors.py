"""Exception taxonomy for the TeachIntent Evaluator v0.1.

A flat hierarchy under :class:`EvaluatorError`. Each concrete exception
corresponds to one frozen ``failure_type`` in the evaluator failure taxonomy
(docs/evaluator_spec_v0.1.md Section 30). Generator Layer 0 failures are NOT
part of this taxonomy -- they are valid Generator evaluation outcomes captured
by ``gate_failure`` in the :class:`UniversalEvaluationArtifact`.

Evaluator-owned failures MUST NOT be converted into low D1-D6 scores.

Stages and their failures:

* setup input contract (jsonschema) -> :class:`SetupInputJsonSchemaError`
* setup input contract (pydantic)  -> :class:`SetupInputPydanticError`
* setup run context                -> :class:`SetupRunContextError`
* setup judge config               -> :class:`SetupJudgeConfigError`
* judge API call                   -> :class:`JudgeAPIError`
* judge response parsing           -> :class:`JudgeResponseParseError`
* judge output schema              -> :class:`JudgeOutputSchemaError`
* evidence source/resolution       -> :class:`EvidenceSourceError`
* evidence text grounding           -> :class:`EvidenceGroundingError`
* other evaluator implementation   -> :class:`InternalEvaluatorError`
"""

from __future__ import annotations

__all__ = [
    "EvaluatorError",
    "SetupInputJsonSchemaError",
    "SetupInputPydanticError",
    "SetupRunContextError",
    "SetupJudgeConfigError",
    "JudgeAPIError",
    "JudgeResponseParseError",
    "JudgeOutputSchemaError",
    "EvidenceSourceError",
    "EvidenceGroundingError",
    "InternalEvaluatorError",
]

# Frozen failure_type enum (docs/evaluator_spec_v0.1.md Section 30).
SETUP_INPUT_JSONSCHEMA_ERROR = "setup_input_jsonschema_error"
SETUP_INPUT_PYDANTIC_ERROR = "setup_input_pydantic_error"
SETUP_RUN_CONTEXT_ERROR = "setup_run_context_error"
SETUP_JUDGE_CONFIG_ERROR = "setup_judge_config_error"
JUDGE_API_ERROR = "judge_api_error"
JUDGE_RESPONSE_PARSE_ERROR = "judge_response_parse_error"
JUDGE_OUTPUT_SCHEMA_ERROR = "judge_output_schema_error"
EVIDENCE_SOURCE_ERROR = "evidence_source_error"
EVIDENCE_GROUNDING_ERROR = "evidence_grounding_error"
INTERNAL_EVALUATOR_ERROR = "internal_evaluator_error"


class EvaluatorError(Exception):
    """Base class for all evaluator-owned failures.

    Each subclass carries a ``failure_type`` attribute matching the frozen
    enum and a ``summary`` attribute (non-empty, MUST NOT contain secrets).
    """

    failure_type: str = INTERNAL_EVALUATOR_ERROR

    def __init__(self, summary: str) -> None:
        self.summary = summary
        super().__init__(summary)


class SetupInputJsonSchemaError(EvaluatorError):
    """TeachIntent input fails canonical input JSON Schema."""

    failure_type = SETUP_INPUT_JSONSCHEMA_ERROR


class SetupInputPydanticError(EvaluatorError):
    """TeachIntent input fails canonical Pydantic validation."""

    failure_type = SETUP_INPUT_PYDANTIC_ERROR


class SetupRunContextError(EvaluatorError):
    """EvaluationRunContext is invalid."""

    failure_type = SETUP_RUN_CONTEXT_ERROR


class SetupJudgeConfigError(EvaluatorError):
    """JudgeConfig is invalid."""

    failure_type = SETUP_JUDGE_CONFIG_ERROR


class JudgeAPIError(EvaluatorError):
    """Judge network/provider/non-success/malformed provider payload failure.

    Attributes:
        response_text: full HTTP response body when available; may be None
            for network errors. Never contains the API key.
        status_code: HTTP status code if a response was received, else None.
    """

    failure_type = JUDGE_API_ERROR

    def __init__(
        self,
        summary: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(summary)


class JudgeResponseParseError(EvaluatorError):
    """Text judge response cannot be parsed under Section 22.

    Attributes:
        raw_text: the exact judge output text (for the judge_raw_response.txt
            artifact).
    """

    failure_type = JUDGE_RESPONSE_PARSE_ERROR

    def __init__(self, summary: str, *, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__(summary)


class JudgeOutputSchemaError(EvaluatorError):
    """Parsed judge object violates frozen JudgeOutput shape/types/enums.

    Attributes:
        raw_text: the exact judge output text (when available).
    """

    failure_type = JUDGE_OUTPUT_SCHEMA_ERROR

    def __init__(self, summary: str, *, raw_text: str | None = None) -> None:
        self.raw_text = raw_text
        super().__init__(summary)


class EvidenceSourceError(EvaluatorError):
    """Evidence source syntax/resolution invalid."""

    failure_type = EVIDENCE_SOURCE_ERROR


class EvidenceGroundingError(EvaluatorError):
    """Evidence text not grounded in resolved source."""

    failure_type = EVIDENCE_GROUNDING_ERROR


class InternalEvaluatorError(EvaluatorError):
    """Other evaluator implementation failure."""

    failure_type = INTERNAL_EVALUATOR_ERROR
