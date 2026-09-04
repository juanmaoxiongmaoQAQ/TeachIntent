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


class HealthResponse(BaseModel):
    status: str
    application: str


class GenerateRequest(BaseModel):
    content_anchor: str
    teaching_scenario: str
    learner_utterance: str | None = None
    learner_level: str
    knowledge_state: str
    affective_state: str | None = None
    pedagogical_intent: Literal[
        "elicitation",
        "scaffolding",
        "explanation",
        "corrective_feedback",
        "supportive_feedback",
        "extension",
    ]


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


class ErrorDetail(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
