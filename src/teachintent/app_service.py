"""Framework-independent application service for the TeachIntent web app.

This module is the boundary between presentation layers and the research core.
It reads committed examples plus portable public demo evaluator artifacts only.
It does not import Gradio, FastAPI, or git-ignored historical ``results/``.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable, Literal
from uuid import uuid4

from dotenv import load_dotenv
from pydantic import ValidationError

from . import demo
from .evaluator import DIMENSIONS, EvaluationRunContext, evaluate_speech_plan
from .evaluator_diagnostic.confirmatory_runner import (
    build_confirmatory_judge,
    build_frozen_judge_config,
)
from .generator import GeneratorError, SpeechPlanGenerationResult
from .models import TeachIntentInput
from .validators import iter_input_errors
from .web_models import (
    CriticalFlag,
    DimensionEvaluation,
    EvaluationResponse,
    EvidenceItem,
    ExampleSummary,
    GenerateRequest,
    GenerationMetadata,
    LiveEvaluationResponse,
    LiveGenerationResponse,
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
MAX_LIVE_SESSIONS = 64
SAFE_ERROR_PATTERNS = (
    (re.compile(r"Authorization:\s*Bearer\s+\S+"), "[credential]"),
    (re.compile(r"Bearer\s+\S+"), "[credential]"),
    (re.compile(r"sk-[A-Za-z0-9_-]+"), "[credential]"),
    (re.compile(r"HY3_API_KEY=?\S*"), "[credential]"),
    (re.compile(r"OPENROUTER_API_KEY=?\S*"), "[credential]"),
    (re.compile(r"\.env"), "[env-file]"),
    (re.compile(r"/Users/[^\s\"']+"), "[local-path]"),
    (re.compile(r"/mnt/[^\s\"']+"), "[local-path]"),
)

EvidenceSourceClass = Literal["context", "speech_plan", "unknown"]
GenerationRunner = Callable[[dict[str, Any], str], SpeechPlanGenerationResult]
EvaluationRunner = Callable[
    [dict[str, Any], str, EvaluationRunContext], Any
]


class AppServiceError(ValueError):
    """Base error for application service boundary failures."""


class ExampleNotFound(AppServiceError):
    """Raised when a requested public example is not part of the Explore set."""


class LiveSessionNotFound(AppServiceError):
    """Raised when a live generation session id is unknown."""


class LiveGenerationError(AppServiceError):
    """Raised when live generation fails with a sanitized summary."""

    def __init__(self, failure_type: str, summary: str):
        super().__init__(summary)
        self.failure_type = failure_type
        self.summary = summary


@dataclass
class LiveSession:
    input_doc: dict[str, Any]
    plan_doc: dict[str, Any]
    raw_response: str
    prompt_version: str
    generation: GenerationMetadata
    evaluation: EvaluationResponse | None = None


class LiveSessionStore:
    """Small bounded in-memory store for live app sessions."""

    def __init__(self, max_sessions: int = MAX_LIVE_SESSIONS):
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, LiveSession] = OrderedDict()

    def create(self, session: LiveSession) -> str:
        session_id = str(uuid4())
        self._sessions[session_id] = session
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return session_id

    def get(self, session_id: str) -> LiveSession:
        try:
            session = self._sessions[session_id]
        except KeyError as exc:
            raise LiveSessionNotFound(f"Unknown live session: {session_id}") from exc
        self._sessions.move_to_end(session_id)
        return session

    def clear(self) -> None:
        self._sessions.clear()

    def __len__(self) -> int:
        return len(self._sessions)


LIVE_SESSION_STORE = LiveSessionStore()


def sanitize_error_summary(value: Any) -> str:
    summary = str(value)
    for pattern, replacement in SAFE_ERROR_PATTERNS:
        summary = pattern.sub(replacement, summary)
    return summary[:500]


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

    metadata = artifact.get("run_metadata") or {}
    return EvaluationResponse(
        available=True,
        evaluator_version=str(artifact.get("evaluator_version", "")),
        judge_prompt_version=str(
            artifact.get("judge_prompt_version")
            or metadata.get("judge_prompt_version")
            or ""
        ),
        source_run_id=str(artifact.get("source_run_id") or ""),
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


def build_live_input_doc(request: GenerateRequest) -> dict[str, Any]:
    """Build the canonical TeachIntent input document for Live Studio."""
    input_doc: dict[str, Any] = {
        "schema_version": "1.0.0-rc.2",
        "output_language": "zh-CN",
        "instructional_content": {
            "content_anchor": request.content_anchor.strip(),
        },
        "pedagogical_context": {
            "scenario": request.teaching_scenario.strip(),
        },
        "learner": {
            "level": request.learner_level.strip(),
            "knowledge_state": request.knowledge_state.strip(),
        },
        "pedagogical_intent": {
            "primary": request.pedagogical_intent,
        },
    }
    learner_utterance = (request.learner_utterance or "").strip()
    if learner_utterance:
        input_doc["pedagogical_context"]["learner_utterance"] = learner_utterance
    affective_state = (request.affective_state or "").strip()
    if affective_state:
        input_doc["learner"]["affective_state"] = affective_state
    return input_doc


def validate_live_input_doc(input_doc: dict[str, Any]) -> None:
    errors = iter_input_errors(input_doc)
    if errors:
        details = "; ".join(f"{error.json_path}: {error.message}" for error in errors)
        raise LiveGenerationError("input_validation_error", details)
    try:
        TeachIntentInput.model_validate(input_doc)
    except ValidationError as exc:
        raise LiveGenerationError(
            "input_validation_error",
            sanitize_error_summary(exc),
        ) from exc


def _default_generation_runner(
    input_doc: dict[str, Any],
    prompt_version: str,
) -> SpeechPlanGenerationResult:
    return demo.run_live_generation_result(input_doc, prompt_version)


def generate_live_workbench(
    request: GenerateRequest,
    *,
    session_store: LiveSessionStore = LIVE_SESSION_STORE,
    generation_runner: GenerationRunner | None = None,
) -> LiveGenerationResponse:
    """Generate one live Speech Plan and retain true raw_response in memory."""
    input_doc = build_live_input_doc(request)
    validate_live_input_doc(input_doc)
    runner = generation_runner or _default_generation_runner
    try:
        result = runner(input_doc, DEFAULT_PROMPT_VERSION)
    except GeneratorError as exc:
        raise LiveGenerationError(
            type(exc).__name__,
            sanitize_error_summary(exc),
        ) from exc
    except Exception as exc:
        raise LiveGenerationError(
            type(exc).__name__,
            sanitize_error_summary(exc),
        ) from exc

    generation = GenerationMetadata(
        prompt_version=result.prompt_version,
        requested_model=result.requested_model,
        reported_model=result.reported_model,
        duration_seconds=round(result.duration_seconds, 3),
    )
    session = LiveSession(
        input_doc=input_doc,
        plan_doc=result.plan_doc,
        raw_response=result.raw_response,
        prompt_version=result.prompt_version,
        generation=generation,
    )
    session_id = session_store.create(session)
    return LiveGenerationResponse(
        session_id=session_id,
        input=input_doc,
        speech_plan=result.plan_doc,
        generation=generation,
    )


def _default_evaluation_runner(
    input_doc: dict[str, Any],
    raw_response: str,
    run_context: EvaluationRunContext,
) -> Any:
    load_dotenv(REPO_ROOT / ".env")
    judge = build_confirmatory_judge()
    if judge is None:
        return {
            "available": False,
            "failure_type": "setup_judge_config_error",
            "failure_summary": "OPENROUTER_API_KEY is not configured in local environment.",
        }
    judge_config = build_frozen_judge_config(judge)
    return evaluate_speech_plan(
        input_doc,
        raw_response,
        run_context,
        judge_config,
        judge,
    )


def _evaluator_result_to_evaluation_response(result: Any) -> EvaluationResponse:
    if isinstance(result, EvaluationResponse):
        return result
    if isinstance(result, dict):
        if result.get("available") is False:
            summary = sanitize_error_summary(
                result.get("failure_summary")
                or result.get("reason")
                or "The independent evaluator did not return a usable artifact."
            )
            return EvaluationResponse(
                available=False,
                reason=summary,
                failure_type=str(result.get("failure_type") or "evaluator_unavailable"),
                failure_summary=summary,
            )
        artifact = result.get("artifact") if "artifact" in result else result
    else:
        if getattr(result, "failure", None) is not None:
            failure = result.failure
            summary = sanitize_error_summary(failure.summary)
            return EvaluationResponse(
                available=False,
                reason=summary,
                failure_type=failure.failure_type,
                failure_summary=summary,
            )
        artifact_model = getattr(result, "artifact", None)
        if artifact_model is None:
            return EvaluationResponse(
                available=False,
                reason="The independent evaluator did not return a usable artifact.",
                failure_type="internal_evaluator_error",
                failure_summary=(
                    "The independent evaluator did not return a usable artifact."
                ),
            )
        artifact = artifact_model.model_dump(mode="json")

    if not artifact.get("structural_valid", True) or not artifact.get("scores"):
        gate = artifact.get("gate_failure") or {}
        summary = "Generator raw response did not pass evaluator Layer-0 gate."
        if gate.get("stage") or gate.get("summary"):
            summary = f"{summary} {gate.get('stage', '')}: {gate.get('summary', '')}"
        summary = sanitize_error_summary(summary)
        return EvaluationResponse(
            available=False,
            reason=summary,
            failure_type="evaluator_layer0_gate_failure",
            failure_summary=summary,
        )

    response = _artifact_to_evaluation_response(artifact)
    if response.available:
        response.source_run_id = None
    return response


def evaluate_live_session(
    session_id: str,
    *,
    session_store: LiveSessionStore = LIVE_SESSION_STORE,
    evaluation_runner: EvaluationRunner | None = None,
) -> LiveEvaluationResponse:
    """Evaluate a live session using its stored true generator raw_response."""
    session = session_store.get(session_id)
    if session.evaluation is None:
        runner = evaluation_runner or _default_evaluation_runner
        run_context = EvaluationRunContext(
            input_case_id=f"live-{session_id}",
            generator_version="v0.1",
            prompt_version=session.prompt_version,
        )
        try:
            result = runner(session.input_doc, session.raw_response, run_context)
            session.evaluation = _evaluator_result_to_evaluation_response(result)
        except Exception as exc:
            summary = sanitize_error_summary(exc)
            session.evaluation = EvaluationResponse(
                available=False,
                reason=summary,
                failure_type=type(exc).__name__,
                failure_summary=summary,
            )
    return LiveEvaluationResponse(session_id=session_id, evaluation=session.evaluation)


__all__ = [
    "AppServiceError",
    "DEFAULT_PROMPT_VERSION",
    "EXPLORE_EXAMPLES",
    "ExampleNotFound",
    "PUBLIC_DEMO_ARTIFACT_VERSION",
    "PUBLIC_DEMO_EVALUATOR_ARTIFACT_DIR",
    "RECOMMENDED_EXAMPLE",
    "LIVE_SESSION_STORE",
    "LiveGenerationError",
    "LiveSession",
    "LiveSessionNotFound",
    "LiveSessionStore",
    "build_recorded_workbench",
    "build_live_input_doc",
    "classify_evidence_source",
    "evaluate_live_session",
    "extract_dimension_evidence",
    "generate_live_workbench",
    "get_example",
    "get_recorded_evaluation",
    "list_examples",
    "sanitize_error_summary",
    "validate_live_input_doc",
]
