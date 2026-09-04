"""Typed response models for the TeachIntent FastAPI boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    source: str
    text: str


class DimensionEvaluation(BaseModel):
    score: int | float
    evidence: list[EvidenceItem]
    brief_justification: str


class CriticalFlag(BaseModel):
    flag: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    brief_justification: str = ""


class EvaluationResponse(BaseModel):
    available: bool
    evaluator_version: str | None = None
    judge_prompt_version: str | None = None
    source_run_id: str | None = None
    scores: dict[str, DimensionEvaluation] = Field(default_factory=dict)
    critical_flags: list[CriticalFlag] = Field(default_factory=list)
    reason: str | None = None
    failure_type: str | None = None
    failure_summary: str | None = None


class SupportedControl(BaseModel):
    path: str
    value: Any
    instruction_fragment: str
    realization: str


class UnsupportedControl(BaseModel):
    path: str
    value: Any
    reason: str


class DeliveryAdapterInfo(BaseModel):
    instruct: str
    supported_controls: list[SupportedControl] = Field(default_factory=list)
    unsupported_controls: list[UnsupportedControl] = Field(default_factory=list)


class VoiceCondition(BaseModel):
    instruct: str
    audio_file: str
    audio_url: str
    audio_sha256: str
    duration_seconds: float


class VoiceRealizationResponse(BaseModel):
    available: bool
    mode: Literal["recorded"] = "recorded"
    reason: str | None = None
    exact_verbal_text: str | None = None
    exact_verbal_text_sha256: str | None = None
    speaker: str | None = None
    model: str | None = None
    language: str | None = None
    seed: int | None = None
    delivery_adapter: DeliveryAdapterInfo | None = None
    ab_invariants: dict[str, Any] = Field(default_factory=dict)
    neutral: VoiceCondition | None = None
    planned: VoiceCondition | None = None
    limitations: list[str] = Field(default_factory=list)


class ExampleSummary(BaseModel):
    id: str
    title: str
    description: str
    recommended: bool = False


class WorkbenchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example: ExampleSummary
    prompt_version: str
    input: dict[str, Any]
    speech_plan: dict[str, Any]
    evaluation: EvaluationResponse
    voice_realization: VoiceRealizationResponse


class HealthResponse(BaseModel):
    status: str
    application: str


PedagogicalIntent = Literal[
    "elicitation",
    "scaffolding",
    "explanation",
    "corrective_feedback",
    "supportive_feedback",
    "extension",
]


class GenerateRequest(BaseModel):
    content_anchor: str
    teaching_scenario: str
    learner_utterance: str | None = None
    learner_level: str
    knowledge_state: str
    affective_state: str | None = None
    pedagogical_intent: PedagogicalIntent


class GenerationMetadata(BaseModel):
    prompt_version: str
    requested_model: str
    reported_model: str | None = None
    duration_seconds: float


class LiveGenerationResponse(BaseModel):
    session_id: str
    mode: Literal["live"] = "live"
    input: dict[str, Any]
    speech_plan: dict[str, Any]
    generation: GenerationMetadata
    evaluation: None = None


class EvaluateRequest(BaseModel):
    session_id: str


class LiveEvaluationResponse(BaseModel):
    session_id: str
    evaluation: EvaluationResponse


class IntentCompareRequest(BaseModel):
    content_anchor: str
    teaching_scenario: str
    learner_utterance: str | None = None
    learner_level: str
    knowledge_state: str
    affective_state: str | None = None
    left_intent: PedagogicalIntent
    right_intent: PedagogicalIntent


class ComparisonInvariants(BaseModel):
    changed_input_field: Literal["input.pedagogical_intent.primary"]
    left_intent: PedagogicalIntent
    right_intent: PedagogicalIntent
    all_other_input_fields_equal: bool
    prompt_version: str
    same_prompt_version: bool
    same_requested_model: bool


class CompareGenerationResult(BaseModel):
    input: dict[str, Any]
    speech_plan: dict[str, Any]
    generation: GenerationMetadata


class StructuralContrast(BaseModel):
    verbal_segments: dict[str, int]
    delivery_decision: dict[str, Literal["default", "selective"]]
    verbal_text_identical: bool
    delivery_plan_identical: bool
    left_control_paths: list[str]
    right_control_paths: list[str]


class IntentCompareResponse(BaseModel):
    mode: Literal["intent_compare"]
    comparison: ComparisonInvariants
    base_context: dict[str, Any]
    left: CompareGenerationResult
    right: CompareGenerationResult
    structural_contrast: StructuralContrast


class ErrorDetail(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
