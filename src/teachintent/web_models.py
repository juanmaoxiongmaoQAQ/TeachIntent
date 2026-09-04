"""Typed response models for the TeachIntent FastAPI boundary."""

from __future__ import annotations

from typing import Any

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
