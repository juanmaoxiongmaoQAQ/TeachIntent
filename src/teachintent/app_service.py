"""Framework-independent application service for the TeachIntent web app.

This module is the boundary between presentation layers and the research core.
It reads committed examples plus portable public demo evaluator artifacts only.
It does not import Gradio, FastAPI, or git-ignored historical ``results/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from . import demo
from .evaluator import DIMENSIONS
from .web_models import (
    CriticalFlag,
    DimensionEvaluation,
    EvaluationResponse,
    EvidenceItem,
    ExampleSummary,
    WorkbenchResponse,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR = (
    REPO_ROOT / "public_demo" / "evaluator_artifacts"
)
PUBLIC_DEMO_ARTIFACT_VERSION = "public-demo-evaluator-artifact-v1"
DEFAULT_PROMPT_VERSION = "v0.2"
RECOMMENDED_EXAMPLE = "corrective-feedback"
EXPLORE_EXAMPLES = (
    "corrective-feedback",
    "scaffolding",
    "supportive-feedback",
)

EvidenceSourceClass = Literal["context", "speech_plan", "unknown"]


class AppServiceError(ValueError):
    """Base error for application service boundary failures."""


class ExampleNotFound(AppServiceError):
    """Raised when a requested public example is not part of the Explore set."""


def _public_artifact_path(example_name: str, prompt_version: str) -> Path:
    return PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR / (
        f"{example_name}.{prompt_version.replace('.', '_')}.json"
    )


def _load_public_evaluator_artifact(
    example_name: str,
    prompt_version: str,
) -> dict[str, Any] | None:
    path = _public_artifact_path(example_name, prompt_version)
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if artifact.get("artifact_version") != PUBLIC_DEMO_ARTIFACT_VERSION:
        return None
    if artifact.get("example_name") != example_name:
        return None
    if artifact.get("prompt_version") != prompt_version:
        return None
    return artifact


def _example_summary(example_name: str, example: dict[str, Any]) -> ExampleSummary:
    return ExampleSummary(
        id=example_name,
        title=str(example["title"]),
        description=str(example["description"]),
        recommended=example_name == RECOMMENDED_EXAMPLE,
    )


def _load_explore_example(
    example_name: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict[str, Any]:
    if example_name not in EXPLORE_EXAMPLES:
        raise ExampleNotFound(f"Unknown example: {example_name}")
    try:
        return demo.load_recorded_example(example_name, prompt_version)
    except demo.DemoDataError as exc:
        raise AppServiceError(str(exc)) from exc


def _evidence_items(items: Any) -> list[EvidenceItem]:
    if not isinstance(items, list):
        return []
    evidence: list[EvidenceItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence.append(
            EvidenceItem(
                source=str(item.get("source", "")),
                text=str(item.get("text", "")),
            )
        )
    return evidence


def _critical_flags(flags: Any) -> list[CriticalFlag]:
    if not isinstance(flags, list):
        return []
    public_flags: list[CriticalFlag] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        public_flags.append(
            CriticalFlag(
                flag=str(flag.get("flag", "")),
                evidence=_evidence_items(flag.get("evidence")),
                brief_justification=str(flag.get("brief_justification", "")),
            )
        )
    return public_flags


def _artifact_to_evaluation_response(
    artifact: dict[str, Any] | None,
) -> EvaluationResponse:
    if artifact is None:
        return EvaluationResponse(
            available=False,
            reason="Recorded evaluator artifact unavailable.",
        )

    scores: dict[str, DimensionEvaluation] = {}
    raw_scores = artifact.get("scores")
    if not isinstance(raw_scores, dict):
        return EvaluationResponse(
            available=False,
            reason="Recorded evaluator artifact unavailable.",
        )

    for dimension_id, _label in DIMENSIONS:
        score_obj = raw_scores.get(dimension_id)
        if not isinstance(score_obj, dict):
            return EvaluationResponse(
                available=False,
                reason="Recorded evaluator artifact unavailable.",
            )
        evidence = _evidence_items(score_obj.get("evidence"))
        justification = str(score_obj.get("brief_justification", ""))
        if "score" not in score_obj or not evidence or not justification:
            return EvaluationResponse(
                available=False,
                reason="Recorded evaluator artifact unavailable.",
            )
        scores[dimension_id] = DimensionEvaluation(
            score=score_obj["score"],
            evidence=evidence,
            brief_justification=justification,
        )

    return EvaluationResponse(
        available=True,
        evaluator_version=str(artifact.get("evaluator_version", "")),
        judge_prompt_version=str(artifact.get("judge_prompt_version", "")),
        source_run_id=str(artifact.get("source_run_id", "")),
        scores=scores,
        critical_flags=_critical_flags(artifact.get("critical_flags")),
    )


def list_examples() -> list[ExampleSummary]:
    """List the public Explore examples."""
    summaries: list[ExampleSummary] = []
    for example_name in EXPLORE_EXAMPLES:
        example = _load_explore_example(example_name, DEFAULT_PROMPT_VERSION)
        summaries.append(_example_summary(example_name, example))
    return summaries


def get_example(
    example_name: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict[str, Any]:
    """Load one validated recorded example without evaluator expansion."""
    return _load_explore_example(example_name, prompt_version)


def get_recorded_evaluation(
    example_name: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> EvaluationResponse:
    """Load portable recorded Evaluator v0.1 evidence from public_demo only."""
    if example_name not in EXPLORE_EXAMPLES:
        raise ExampleNotFound(f"Unknown example: {example_name}")
    artifact = _load_public_evaluator_artifact(example_name, prompt_version)
    return _artifact_to_evaluation_response(artifact)


def build_recorded_workbench(
    example_name: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> WorkbenchResponse:
    """Build the complete Explore workbench payload for the web app."""
    example = get_example(example_name, prompt_version)
    evaluation = get_recorded_evaluation(example_name, prompt_version)
    return WorkbenchResponse(
        example=_example_summary(example_name, example),
        prompt_version=prompt_version,
        input=example["input"],
        speech_plan=example["speech_plan"],
        evaluation=evaluation,
    )


def extract_dimension_evidence(
    evaluation_artifact: EvaluationResponse | dict[str, Any],
    dimension_id: str,
) -> list[EvidenceItem]:
    """Return all evidence entries for one evaluator dimension."""
    if isinstance(evaluation_artifact, EvaluationResponse):
        score = evaluation_artifact.scores.get(dimension_id)
        return list(score.evidence) if score else []
    score_obj = (evaluation_artifact.get("scores") or {}).get(dimension_id)
    if not isinstance(score_obj, dict):
        return []
    return _evidence_items(score_obj.get("evidence"))


def classify_evidence_source(source: str) -> EvidenceSourceClass:
    """Conservatively classify evaluator evidence source paths."""
    if source.startswith("input."):
        return "context"
    if source.startswith("plan.") or source.startswith("speech_plan."):
        return "speech_plan"
    return "unknown"


__all__ = [
    "AppServiceError",
    "DEFAULT_PROMPT_VERSION",
    "EXPLORE_EXAMPLES",
    "ExampleNotFound",
    "PUBLIC_DEMO_ARTIFACT_VERSION",
    "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
    "RECOMMENDED_EXAMPLE",
    "build_recorded_workbench",
    "classify_evidence_source",
    "extract_dimension_evidence",
    "get_example",
    "get_recorded_evaluation",
    "list_examples",
]
