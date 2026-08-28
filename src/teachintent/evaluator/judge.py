"""Judge backend abstraction and Layer 1 payload sanitation.

The judge backend is abstracted via a :class:`JudgeCompleter` Protocol so the
evaluator is NOT hard-wired to a specific model/provider (Section 27). The
OpenAI-compatible :class:`JudgeClient` reuses the same transport pattern as
the Generator's :class:`Hy3Client` but is an independent class -- the
evaluator judge code never imports from ``teachintent.generator``.

Payload sanitation (Section 6) ensures only the Layer-1-visible subset of the
input + plan reaches the judge. Experiment metadata (block, difficulty,
design_expectations, delivery_need, input_case_id, generator_version,
prompt_version, etc.) is NEVER serialized into the judge prompt.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from .errors import JudgeAPIError

__all__ = [
    "JudgeCompletion",
    "JudgeCompleter",
    "JudgeClient",
    "sanitize_for_judge",
]


@dataclass(frozen=True)
class JudgeCompletion:
    """A single judge completion result.

    Attributes:
        content: the text content returned by the provider (used in
            text-output mode).
        reported_model: the model name AS RETURNED BY THE API (may be None).
        structured_object: the provider-returned structured object, when
            ``structured_output_enabled=true`` and the provider returns one;
            None otherwise.
        finish_reason: the finish_reason from the API, if available.
    """

    content: str
    reported_model: str | None
    structured_object: dict | None
    finish_reason: str | None


@runtime_checkable
class JudgeCompleter(Protocol):
    """Structural typing seam for the judge backend.

    ``model`` is the REQUESTED model (read-only); the REPORTED model is carried
    per-completion on :class:`JudgeCompletion`. ``structured_output_enabled`` is
    the backend's actual structured-output condition (read-only), which the
    service binds against ``JudgeConfig.structured_output_enabled``.
    """

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def structured_output_enabled(self) -> bool: ...

    def complete(
        self, system: str, user: str, *, temperature: float = ...
    ) -> JudgeCompletion: ...


class JudgeClient:
    """OpenAI-compatible Chat Completions client for the judge backend.

    Independent from the Generator's :class:`Hy3Client`. The API key is NEVER
    logged, stored on exceptions, or interpolated into any message.
    """

    DEFAULT_TIMEOUT_SECONDS: float = 120.0

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        response_format: dict[str, Any] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider = provider
        self._timeout = timeout
        self._response_format = response_format
        self._transport = transport

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        """The REQUESTED model. Read-only; for reproducibility metadata."""
        return self._model

    @property
    def structured_output_enabled(self) -> bool:
        """The actual structured-output condition (True iff response_format set)."""
        return self._response_format is not None

    @property
    def endpoint(self) -> str:
        """The full chat-completions endpoint URL (for logging; never the key)."""
        return f"{self._base_url}/chat/completions"

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0
    ) -> JudgeCompletion:
        """Call the judge and return the completion. Sends temperature explicitly."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        structured_object: dict | None = None
        if self._response_format is not None:
            payload["response_format"] = self._response_format

        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            with httpx.Client(
                timeout=self._timeout, transport=self._transport
            ) as http:
                response = http.post(self.endpoint, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise JudgeAPIError(
                f"judge API request failed: {type(exc).__name__}: {exc}"
            ) from exc

        response_text = response.text
        if response.status_code >= 400:
            snippet = response_text[:500]
            raise JudgeAPIError(
                f"judge API returned HTTP {response.status_code}; body snippet: {snippet}",
                status_code=response.status_code,
                response_text=response_text,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise JudgeAPIError(
                f"judge API returned a non-JSON response body: {exc}",
                status_code=response.status_code,
                response_text=response_text,
            ) from exc

        # Top-level payload MUST be a JSON object. A legal JSON value that is
        # a list, string, number, bool, or null is a malformed provider
        # payload -> judge_api_error (NOT internal_evaluator_error).
        if not isinstance(data, dict):
            raise JudgeAPIError(
                f"judge API response top-level is not an object: "
                f"{type(data).__name__}",
                status_code=response.status_code,
                response_text=response_text,
            )

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise JudgeAPIError(
                "judge API response has no non-empty 'choices' array",
                status_code=response.status_code,
                response_text=response_text,
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise JudgeAPIError(
                "judge API response choices[0] is not an object",
                status_code=response.status_code,
                response_text=response_text,
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise JudgeAPIError(
                "judge API response choices[0].message is not an object",
                status_code=response.status_code,
                response_text=response_text,
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            # Malformed provider payload: content missing or not a string or
            # empty. This is a judge_api_error, NOT judge_response_parse_error
            # (the latter is only for when the provider returned valid text
            # that fails the judge response parser).
            finish_reason = first.get("finish_reason")
            hint = (
                f" (finish_reason={finish_reason!r})"
                if finish_reason is not None
                else ""
            )
            raise JudgeAPIError(
                f"judge API response choices[0].message.content is missing, "
                f"not a string, or empty{hint}",
                status_code=response.status_code,
                response_text=response_text,
            )

        # When structured output is requested, the provider may return the
        # structured object via message.content (as a JSON string) or via a
        # dedicated field. We attempt to extract it; if not present, it
        # remains None and the text path handles parsing.
        if self._response_format is not None and content.strip():
            try:
                maybe_obj = json.loads(content)
                if isinstance(maybe_obj, dict):
                    structured_object = maybe_obj
            except json.JSONDecodeError:
                pass

        reported_model = data.get("model")
        if reported_model is not None:
            if not isinstance(reported_model, str):
                raise JudgeAPIError(
                    f"judge API response 'model' field is not a string: "
                    f"{reported_model!r}",
                    status_code=response.status_code,
                    response_text=response_text,
                )
            if not reported_model.strip():
                raise JudgeAPIError(
                    "judge API response 'model' field is empty or whitespace",
                    status_code=response.status_code,
                    response_text=response_text,
                )

        return JudgeCompletion(
            content=content,
            reported_model=reported_model,
            structured_object=structured_object,
            finish_reason=first.get("finish_reason"),
        )


# ---------------------------------------------------------------------------
# Layer 1 payload sanitation (Section 6).
# ---------------------------------------------------------------------------
# Fields the judge MAY inspect from the input.
_INPUT_VISIBLE_KEYS = (
    "output_language",
    "instructional_content",
    "pedagogical_context",
    "learner",
    "pedagogical_intent",
)
# Fields the judge MAY inspect from the plan.
_PLAN_VISIBLE_KEYS = (
    "verbal_plan",
    "delivery_plan",
)


def sanitize_for_judge(input_doc: dict, plan_doc: dict) -> dict:
    """Build the Layer-1-visible payload from the validated input + plan.

    Only the following reach the judge (Section 6.1):

    Input:
        output_language, instructional_content, pedagogical_context,
        learner, pedagogical_intent
    Plan:
        verbal_plan, delivery_plan

    Everything else (schema_version, block, difficulty, tags,
    design_expectations, delivery_need, input_case_id, generator_version,
    prompt_version, etc.) is excluded. The input/plan are deep-copied so the
    returned payload shares no mutable state with the originals.
    """
    sanitized_input: dict[str, Any] = {}
    for key in _INPUT_VISIBLE_KEYS:
        if key in input_doc:
            sanitized_input[key] = copy.deepcopy(input_doc[key])

    sanitized_plan: dict[str, Any] = {}
    for key in _PLAN_VISIBLE_KEYS:
        if key in plan_doc:
            sanitized_plan[key] = copy.deepcopy(plan_doc[key])

    return {"input": sanitized_input, "plan": sanitized_plan}
