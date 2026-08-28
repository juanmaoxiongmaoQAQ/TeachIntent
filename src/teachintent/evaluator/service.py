"""Evaluator v0.1 main orchestration service.

Pipeline (docs/evaluator_spec_v0.1.md Section 8)::

    Setup validation (ordered)
      1. validate EvaluationRunContext (Pydantic)
      2. validate JudgeConfig (Pydantic + prompt hash content + retry/self-repair rejection)
      3. prompt hash content verification + backend provenance binding
      4. validate TeachIntent input (reuse canonical Input JSON Schema + Pydantic)
            |
            v
    Layer 0 — Canonical Generator-Output Contract Gate
      |- parse_speech_plan_json (reuse Generator parser)
      |- iter_speech_plan_errors (reuse Generator JSON Schema validator)
      |- SpeechPlan.model_validate (reuse Generator Pydantic validator)
            |
            |- invalid -> UniversalEvaluationArtifact(structural_valid=false)
            |
            v
    Layer 1 — Universal Semantic Judge
      |- sanitize_for_judge (Layer 1 isolation)
      |- build_judge_prompt (frozen v0.1)
      |- judge.complete (single call; no retry/self-repair in v0.1)
      |- parse_judge_response / structured object
      |- JudgeOutput validation (shape + evidence + critical-flag uniqueness)
      |- deterministic overall_score computation
            |
            v
    UniversalEvaluationArtifact

Evaluator-owned failures at any evaluator step produce an
EvaluatorFailureArtifact, not low semantic scores (Section 30).

Layer 0 reuses the EXACT same canonical parser and validators as the Generator
pipeline -- no duplication, no relaxation (Section 9.2).

Setup validation accepts ``EvaluationRunContext | dict`` and
``JudgeConfig | dict`` and validates at the service boundary, so callers
cannot bypass validation by constructing models externally.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Union

from pydantic import ValidationError

from ..generator.errors import ResponseParsingError
from ..generator.parser import parse_speech_plan_json
from ..models import SpeechPlan, TeachIntentInput
from ..validators import iter_input_errors, iter_speech_plan_errors
from .errors import (
    EvaluatorError,
    EvidenceGroundingError,
    EvidenceSourceError,
    InternalEvaluatorError,
    JudgeAPIError,
    JudgeOutputSchemaError,
    JudgeResponseParseError,
    SetupInputJsonSchemaError,
    SetupInputPydanticError,
    SetupJudgeConfigError,
    SetupRunContextError,
)
from .evidence import validate_evidence
from .judge import JudgeCompleter, sanitize_for_judge
from .models import (
    DimensionJudgment,
    EvaluatorFailureArtifact,
    EvaluationRunContext,
    GateFailure,
    JudgeConfig,
    JudgeOutput,
    RunMetadata,
    UniversalEvaluationArtifact,
)
from .parser import parse_judge_response
from .prompt import build_judge_prompt, compute_judge_prompt_sha256
from .rubric import (
    DIMENSION_IDS,
    EVALUATOR_VERSION,
    compute_overall_score,
)

__all__ = ["EvaluatorResult", "evaluate_speech_plan"]

# Type alias: the service accepts either a pre-validated model or a raw dict.
RunContextInput = Union[EvaluationRunContext, dict]
JudgeConfigInput = Union[JudgeConfig, dict]


@dataclass(frozen=True)
class EvaluatorResult:
    """The outcome of one evaluation run.

    Exactly one of ``artifact`` or ``failure`` is non-None:
    * ``artifact`` is set for a valid Generator structural outcome (pass or
      gate-fail) or a successful Layer 1 evaluation;
    * ``failure`` is set for an evaluator-owned/setup failure
      (EvaluatorFailureArtifact).

    When ``artifact`` is a :class:`UniversalEvaluationArtifact` with
    ``structural_valid=false``, no judge call was made (Layer 0 gate fail).
    """

    artifact: UniversalEvaluationArtifact | None = None
    failure: EvaluatorFailureArtifact | None = None
    judge_raw_response: str | None = None


def _canonical_utc_now() -> str:
    """Return canonical UTC ISO-8601 timestamp: ``YYYY-MM-DDTHH:MM:SSZ``.

    Uses ``strftime`` to avoid the ``+00:00`` offset that
    ``isoformat()`` produces for timezone-aware datetimes.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_raw_dict(value: Union[Any, dict]) -> dict:
    """Coerce a pre-constructed Pydantic model to a raw dict for re-validation.

    ``model_construct()`` bypasses validation, so even when the caller passes
    an already-constructed :class:`EvaluationRunContext` or :class:`JudgeConfig`
    instance, we MUST re-validate it through ``model_validate``. To do so we
    first dump it back to a raw dict (when it is a model instance).
    """
    if isinstance(value, (EvaluationRunContext, JudgeConfig)):
        # Serialize the model (model_dump bypasses validation too, but gives us
        # the raw field values to re-validate).
        return value.model_dump()
    return value


def evaluate_speech_plan(
    input_doc: dict,
    raw_response: str,
    run_context: RunContextInput,
    judge_config: JudgeConfigInput,
    judge: JudgeCompleter,
) -> EvaluatorResult:
    """Evaluate one Generator raw response against the validated input.

    *input_doc* is the validated TeachIntent input document (dict).
    *raw_response* is the raw Generator response text to evaluate.
    *run_context* accepts ``EvaluationRunContext | dict`` -- always re-validated
    at the service boundary (including already-constructed model instances,
    which ``model_construct()`` could have bypassed).
    *judge_config* accepts ``JudgeConfig | dict`` -- always re-validated at the
    service boundary, including prompt hash content verification and backend
    provenance binding.
    *judge* is the injected judge backend (must satisfy
    :class:`JudgeCompleter`).

    Setup validation order:
    1. run context (Pydantic, always re-validated)
    2. judge config (Pydantic + retry/self-repair rejection + prompt hash content)
    3. backend provenance binding (provider + model + structured_output)
    4. TeachIntent input (reuse canonical pipeline)
    5. Layer 0 gate
    6. Layer 1 judge

    Returns an :class:`EvaluatorResult`.
    """
    run_started = _canonical_utc_now()

    # ---- Setup step 1: validate EvaluationRunContext (always re-validate) ----
    raw_ctx = _to_raw_dict(run_context)
    try:
        ctx = EvaluationRunContext.model_validate(raw_ctx)
    except ValidationError as exc:
        return _make_setup_failure(
            SetupRunContextError(f"EvaluationRunContext invalid: {exc}"),
            input_case_id=_safe_extract_case_id(raw_ctx),
            run_metadata=None,
        )
    except Exception as exc:
        return _make_setup_failure(
            SetupRunContextError(f"EvaluationRunContext invalid: {type(exc).__name__}: {exc}"),
            input_case_id=_safe_extract_case_id(raw_ctx),
            run_metadata=None,
        )

    # ---- Setup step 2: validate JudgeConfig (always re-validate) ----
    raw_cfg = _to_raw_dict(judge_config)
    try:
        cfg = JudgeConfig.model_validate(raw_cfg)
    except ValidationError as exc:
        return _make_setup_failure(
            SetupJudgeConfigError(f"JudgeConfig invalid: {exc}"),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )
    except Exception as exc:
        return _make_setup_failure(
            SetupJudgeConfigError(f"JudgeConfig invalid: {type(exc).__name__}: {exc}"),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )

    # v0.1: reject retry_enabled=true and self_repair_enabled=true.
    if cfg.retry_enabled or cfg.self_repair_enabled:
        return _make_setup_failure(
            SetupJudgeConfigError(
                "Evaluator v0.1 does not support retry_enabled=true or "
                "self_repair_enabled=true; these conditions are not implemented"
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )

    # Verify prompt hash content matches the frozen Judge Prompt v0.1.
    expected_hash = compute_judge_prompt_sha256()
    if cfg.judge_prompt_sha256 != expected_hash:
        return _make_setup_failure(
            SetupJudgeConfigError(
                f"judge_prompt_sha256 does not match the frozen Judge Prompt "
                f"v0.1 hash; expected {expected_hash}, got {cfg.judge_prompt_sha256}"
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )

    # ---- Setup step 3: backend provenance binding ----
    # The JudgeConfig must match the actual judge backend.
    if cfg.judge_provider != judge.provider:
        return _make_setup_failure(
            SetupJudgeConfigError(
                f"judge_provider mismatch: config={cfg.judge_provider!r}, "
                f"actual judge={judge.provider!r}"
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )
    if cfg.judge_model_requested != judge.model:
        return _make_setup_failure(
            SetupJudgeConfigError(
                f"judge_model_requested mismatch: config={cfg.judge_model_requested!r}, "
                f"actual judge={judge.model!r}"
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )
    if cfg.structured_output_enabled != judge.structured_output_enabled:
        return _make_setup_failure(
            SetupJudgeConfigError(
                f"structured_output_enabled mismatch: "
                f"config={cfg.structured_output_enabled!r}, "
                f"actual judge={judge.structured_output_enabled!r}"
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=None,
        )

    # ---- Setup step 4: validate TeachIntent input (reuse canonical pipeline) ----
    input_doc = copy.deepcopy(input_doc)
    input_errors = iter_input_errors(input_doc)
    if input_errors:
        return _make_setup_failure(
            SetupInputJsonSchemaError(
                "input failed JSON Schema: "
                + "; ".join(f"{e.json_path}: {e.message}" for e in input_errors)
            ),
            input_case_id=ctx.input_case_id,
            run_metadata=_build_run_metadata(ctx, cfg, run_started, judge_model_reported=None),
        )
    try:
        TeachIntentInput.model_validate(input_doc)
    except ValidationError as exc:
        return _make_setup_failure(
            SetupInputPydanticError(f"input failed Pydantic validation: {exc}"),
            input_case_id=ctx.input_case_id,
            run_metadata=_build_run_metadata(ctx, cfg, run_started, judge_model_reported=None),
        )

    # ---- Setup step 5: Layer 0 gate ----
    gate_failure = _layer0_gate(raw_response)
    if gate_failure is not None:
        artifact = UniversalEvaluationArtifact(
            evaluator_version=EVALUATOR_VERSION,
            structural_valid=False,
            gate_failure=gate_failure,
            scores=None,
            critical_flags=[],
            overall_score=None,
            run_metadata=_build_run_metadata(ctx, cfg, run_started, judge_model_reported=None),
        )
        return EvaluatorResult(artifact=artifact, failure=None)

    # Layer 0 passed -- extract the validated plan doc.
    try:
        parsed = parse_speech_plan_json(raw_response)
    except ResponseParsingError:
        raise InternalEvaluatorError("unreachable: parse_speech_plan_json raised after gate passed")

    # ---- Setup step 6: Layer 1 judge ----
    try:
        return _layer1_judge(input_doc, parsed, raw_response, ctx, cfg, judge, run_started)
    except JudgeAPIError as exc:
        # JudgeAPIError is raised when the API call itself fails -- no
        # completion was received, so reported_model is None.
        return _make_post_failure(
            exc,
            input_case_id=ctx.input_case_id,
            run_metadata=_build_run_metadata(ctx, cfg, run_started, judge_model_reported=None),
        )
    except Exception as exc:  # noqa: BLE001 — bugs must not crash silently.
        return _make_post_failure(
            InternalEvaluatorError(f"unexpected error: {type(exc).__name__}: {exc}"),
            input_case_id=ctx.input_case_id,
            run_metadata=_build_run_metadata(ctx, cfg, run_started, judge_model_reported=None),
        )


# ---------------------------------------------------------------------------
# Layer 0 gate (reuses canonical Generator parser + validators).
# ---------------------------------------------------------------------------
def _layer0_gate(raw_response: str) -> GateFailure | None:
    """Run the canonical Generator-output contract gate.

    Returns a :class:`GateFailure` on failure, or None on success. Reuses the
    EXACT same parser and validators as the Generator pipeline (Section 9.2).
    """
    # Stage 1: response_parse
    try:
        parsed = parse_speech_plan_json(raw_response)
    except ResponseParsingError as exc:
        return GateFailure(stage="response_parse", summary=str(exc))

    # Stage 2: json_schema
    plan_errors = iter_speech_plan_errors(parsed)
    if plan_errors:
        summary = "; ".join(f"{e.json_path}: {e.message}" for e in plan_errors)
        return GateFailure(stage="json_schema", summary=summary)

    # Stage 3: pydantic
    try:
        SpeechPlan.model_validate(parsed)
    except ValidationError as exc:
        return GateFailure(stage="pydantic", summary=str(exc))

    return None


# ---------------------------------------------------------------------------
# Layer 1 judge pipeline.
# ---------------------------------------------------------------------------
def _layer1_judge(
    input_doc: dict,
    plan_doc: dict,
    raw_response: str,
    run_context: EvaluationRunContext,
    judge_config: JudgeConfig,
    judge: JudgeCompleter,
    run_started: str,
) -> EvaluatorResult:
    """Run the Layer 1 semantic judge and build the UniversalEvaluationArtifact.

    The reported_model is per-run local state: on a successful judge completion
    it is carried through all post-completion error paths into the
    EvaluatorFailureArtifact's RunMetadata directly, with no module-level
    global. Two concurrent/interleaved runs cannot cross-contaminate.
    """
    # Sanitize the payload (Layer 1 isolation).
    sanitized = sanitize_for_judge(input_doc, plan_doc)

    # Build the frozen judge prompt.
    prompt = build_judge_prompt(sanitized)

    # Single judge call (v0.1: no retry, no self-repair).
    # JudgeAPIError from the call itself -> propagates as judge_api_error with
    # reported_model=None (no completion was received).
    completion = judge.complete(
        system=prompt.system, user=prompt.user, temperature=judge_config.temperature
    )

    # Per-run reported_model captured locally (NOT a module global).
    reported_model = completion.reported_model
    judge_raw = completion.content

    try:
        # Parse the judge response.
        if judge_config.structured_output_enabled and completion.structured_object is not None:
            judge_obj = completion.structured_object
        else:
            judge_obj = parse_judge_response(judge_raw)

        # Validate JudgeOutput shape (Pydantic).
        try:
            judge_output = JudgeOutput.model_validate(judge_obj)
        except ValidationError as exc:
            raise JudgeOutputSchemaError(
                f"judge output violates JudgeOutput contract: {exc}",
                raw_text=judge_raw,
            ) from exc

        # Validate evidence (source + grounding) for all dimensions and flags.
        _validate_all_evidence(judge_output, input_doc, plan_doc)
    except (JudgeResponseParseError, JudgeOutputSchemaError, EvidenceSourceError, EvidenceGroundingError) as exc:
        # Post-judge failure: the completion was received, so carry its
        # reported_model into the failure metadata (per-run local state).
        return _make_post_failure(
            exc,
            input_case_id=run_context.input_case_id,
            run_metadata=_build_run_metadata(
                run_context, judge_config, run_started,
                judge_model_reported=reported_model,
            ),
        )
    except EvaluatorError as exc:
        return _make_post_failure(
            exc,
            input_case_id=run_context.input_case_id,
            run_metadata=_build_run_metadata(
                run_context, judge_config, run_started,
                judge_model_reported=reported_model,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — bugs must not crash silently.
        return _make_post_failure(
            InternalEvaluatorError(f"unexpected error: {type(exc).__name__}: {exc}"),
            input_case_id=run_context.input_case_id,
            run_metadata=_build_run_metadata(
                run_context, judge_config, run_started,
                judge_model_reported=reported_model,
            ),
        )

    # Deterministic overall_score computation.
    score_map = {d: judge_output.scores[d].score for d in DIMENSION_IDS}
    overall_score = compute_overall_score(score_map)

    # Build the UniversalEvaluationArtifact.
    artifact = UniversalEvaluationArtifact(
        evaluator_version=EVALUATOR_VERSION,
        structural_valid=True,
        gate_failure=None,
        scores=judge_output.scores,
        critical_flags=judge_output.critical_flags,
        overall_score=overall_score,
        run_metadata=_build_run_metadata(
            run_context, judge_config, run_started,
            judge_model_reported=reported_model,
        ),
    )
    return EvaluatorResult(artifact=artifact, failure=None, judge_raw_response=judge_raw)


def _validate_all_evidence(
    judge_output: JudgeOutput,
    input_doc: dict,
    plan_doc: dict,
) -> None:
    """Validate every evidence item across all dimensions and critical flags."""
    for dim_id in DIMENSION_IDS:
        dim: DimensionJudgment = judge_output.scores[dim_id]
        for ev in dim.evidence:
            validate_evidence(ev.source, ev.text, input_doc, plan_doc)

    for cf in judge_output.critical_flags:
        for ev in cf.evidence:
            validate_evidence(ev.source, ev.text, input_doc, plan_doc)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
def _build_run_metadata(
    run_context: EvaluationRunContext,
    judge_config: JudgeConfig,
    run_started: str,
    *,
    judge_model_reported: str | None,
) -> RunMetadata:
    """Build the RunMetadata from the run context + judge config."""
    return RunMetadata(
        judge_provider=judge_config.judge_provider,
        judge_model_requested=judge_config.judge_model_requested,
        judge_model_reported=judge_model_reported,
        temperature=judge_config.temperature,
        timestamp=run_started,
        input_case_id=run_context.input_case_id,
        generator_version=run_context.generator_version,
        prompt_version=run_context.prompt_version,
        judge_prompt_version=judge_config.judge_prompt_version,
        judge_prompt_sha256=judge_config.judge_prompt_sha256,
        structured_output_enabled=judge_config.structured_output_enabled,
        retry_enabled=judge_config.retry_enabled,
        self_repair_enabled=judge_config.self_repair_enabled,
    )


def _safe_extract_case_id(run_context: Any) -> str | None:
    """Best-effort extract input_case_id from a possibly-invalid run context."""
    if isinstance(run_context, dict):
        val = run_context.get("input_case_id")
        if isinstance(val, str) and val.strip():
            return val
        return None
    # If it's a model instance (shouldn't happen for the error path, but
    # be defensive), try attribute access.
    try:
        val = getattr(run_context, "input_case_id", None)
        if isinstance(val, str) and val.strip():
            return val
    except Exception:
        pass
    return None


def _make_setup_failure(
    exc: EvaluatorError,
    *,
    input_case_id: str | None,
    run_metadata: RunMetadata | None,
) -> EvaluatorResult:
    """Build an EvaluatorFailureArtifact for setup-phase failures.

    For setup_run_context_error: input_case_id may be null, run_metadata null.
    For setup_judge_config_error: input_case_id may be non-null (if context
    was valid), run_metadata null (config not fully validated).
    For other setup errors (input jsonschema/pydantic): both are non-null.
    """
    artifact = EvaluatorFailureArtifact(
        evaluator_version=EVALUATOR_VERSION,
        input_case_id=input_case_id,
        failure_type=exc.failure_type,  # type: ignore[arg-type]
        summary=exc.summary,
        run_metadata=run_metadata,
    )
    return EvaluatorResult(artifact=None, failure=artifact)


def _make_post_failure(
    exc: EvaluatorError,
    *,
    input_case_id: str,
    run_metadata: RunMetadata,
) -> EvaluatorResult:
    """Build an EvaluatorFailureArtifact for post-setup failures.

    These always carry non-null input_case_id and non-null run_metadata
    (including judge_model_reported when available).
    """
    artifact = EvaluatorFailureArtifact(
        evaluator_version=EVALUATOR_VERSION,
        input_case_id=input_case_id,
        failure_type=exc.failure_type,  # type: ignore[arg-type]
        summary=exc.summary,
        run_metadata=run_metadata,
    )
    return EvaluatorResult(artifact=None, failure=artifact)
