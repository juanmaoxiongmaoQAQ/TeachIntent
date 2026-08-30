"""Speech plan generation service: orchestrates the single-pass pipeline.

Pipeline (docs/speech_plan_schema.md Rule 15 division of labor; no retries, no
self-repair - first-call invalid output preserves Hy3's true instruction-following
signal):

    input dict
      -> iter_input_errors()              (frozen JSON Schema layer)
      -> TeachIntentInput.model_validate  (frozen Pydantic layer)
      -> build_speech_plan_prompt_for_version()  (registry; default v0.1)
      -> client.complete()                (Hy3 API)
      -> parse_speech_plan_json()         (parser; no fixing)
      -> iter_speech_plan_errors()        (frozen JSON Schema layer)
      -> SpeechPlan.model_validate()      (frozen Pydantic layer)
      -> SpeechPlanGenerationResult

Each stage failure raises a distinct exception from :mod:`teachintent.generator.errors`.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from ..models import SpeechPlan, TeachIntentInput
from ..prompts.registry import (
    DEFAULT_PROMPT_VERSION,
    build_speech_plan_prompt_for_version,
    get_speech_plan_prompt_version,
)
from ..validators import iter_input_errors, iter_speech_plan_errors
from .client import Hy3Completer
from .errors import (
    InputContractError,
    ResponseParsingError,
    SpeechPlanSemanticError,
    SpeechPlanStructuralError,
)
from .parser import parse_speech_plan_json

__all__ = ["SpeechPlanGenerationResult", "generate_speech_plan"]


@dataclass(frozen=True)
class SpeechPlanGenerationResult:
    """A successful generation, carrying full reproducibility metadata."""

    speech_plan: SpeechPlan
    plan_doc: dict
    prompt_system: str
    prompt_user: str
    prompt_version: str
    raw_response: str
    requested_model: str
    reported_model: str | None
    started_at: str
    duration_seconds: float


def generate_speech_plan(
    input_doc: dict,
    client: Hy3Completer,
    *,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> SpeechPlanGenerationResult:
    """Generate and fully validate a Speech Plan for *input_doc* using *client*.

    The input dict is validated inside this function (input-contract failure is part
    of this layer's taxonomy) and is never mutated.

    *prompt_version* selects which Generator Prompt builds the system/user messages.
    It defaults to ``"v0.1"`` (the original behavior). An unknown version fails fast
    via :class:`teachintent.prompts.registry.UnknownPromptVersionError` — there is no
    silent fallback. The resolved version is recorded on the result for provenance.
    """
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.monotonic()
    input_doc = copy.deepcopy(input_doc)

    # Stage 1 — input structural validation (JSON Schema layer).
    input_errors = iter_input_errors(input_doc)
    if input_errors:
        raise InputContractError(
            layer="jsonschema",
            error_summary=[f"{e.json_path}: {e.message}" for e in input_errors],
        )

    # Stage 2 — input semantic validation (Pydantic layer).
    try:
        TeachIntentInput.model_validate(input_doc)
    except ValidationError as exc:
        raise InputContractError(
            layer="pydantic",
            error_summary=[str(exc)],
        ) from exc

    # Stage 3 — build the versioned prompt (cannot fail on validated input).
    # Resolve/validate the requested version up front so an unknown version fails
    # fast (before the Hy3 API call) with a clear exception — never a silent
    # fallback to the default. v0.1 is the default, so existing call sites without
    # an explicit version are byte-identical to before.
    resolved_version = get_speech_plan_prompt_version(prompt_version)
    prompt = build_speech_plan_prompt_for_version(input_doc, version=resolved_version)

    # Stage 4 — Hy3 API call.
    completion = client.complete(
        system=prompt.system, user=prompt.user, temperature=0.0
    )
    raw_response = completion.content

    # Stage 5 — parse raw response text into a dict (no fixing).
    parsed = parse_speech_plan_json(raw_response)

    # Stage 6 — output structural validation (JSON Schema layer).
    plan_errors = iter_speech_plan_errors(parsed)
    if plan_errors:
        raise SpeechPlanStructuralError(
            plan_doc=parsed,
            error_summary=[f"{e.json_path}: {e.message}" for e in plan_errors],
            raw_text=raw_response,
        )

    # Stage 7 — output semantic validation (Pydantic layer).
    try:
        speech_plan = SpeechPlan.model_validate(parsed)
    except ValidationError as exc:
        raise SpeechPlanSemanticError(
            plan_doc=parsed,
            error_text=str(exc),
            raw_text=raw_response,
        ) from exc

    # Stage 8 — success.
    duration = time.monotonic() - t0
    return SpeechPlanGenerationResult(
        speech_plan=speech_plan,
        plan_doc=parsed,
        prompt_system=prompt.system,
        prompt_user=prompt.user,
        prompt_version=resolved_version,
        raw_response=raw_response,
        requested_model=client.model,
        reported_model=completion.reported_model,
        started_at=started_at,
        duration_seconds=duration,
    )
