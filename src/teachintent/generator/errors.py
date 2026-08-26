"""Exception taxonomy for the Hy3 speech-plan generation pipeline.

A flat hierarchy under :class:`GeneratorError`. Each concrete exception is raised at
a specific pipeline stage (see ``generator/service.py``) and carries debugging
context as attributes so the smoke runner can record stage artifacts even when the
pipeline fails mid-way. The API key is NEVER included in any message or attribute.

Stages and their failures (docs/speech_plan_schema.md Rule 15 division of labor):

* input contract        -> :class:`InputContractError` (layer = "jsonschema" | "pydantic")
* Hy3 configuration     -> :class:`Hy3ConfigError`
* Hy3 API call          -> :class:`Hy3APIError`
* response parsing      -> :class:`ResponseParsingError`
* output structural     -> :class:`SpeechPlanStructuralError`  (JSON Schema layer)
* output semantic       -> :class:`SpeechPlanSemanticError`    (Pydantic layer)
"""

from __future__ import annotations

__all__ = [
    "GeneratorError",
    "InputContractError",
    "Hy3ConfigError",
    "Hy3APIError",
    "ResponseParsingError",
    "SpeechPlanStructuralError",
    "SpeechPlanSemanticError",
]


class GeneratorError(Exception):
    """Base class for all speech-plan generation failures."""


class InputContractError(GeneratorError):
    """The TeachIntent input failed contract validation.

    Attributes:
        layer: which contract layer failed - ``"jsonschema"`` or ``"pydantic"``.
        error_summary: human-readable summary lines (e.g. ``"<json_path>: <msg>"``
            for jsonschema, formatted pydantic errors for pydantic).
    """

    def __init__(self, layer: str, error_summary: list[str]) -> None:
        self.layer = layer
        self.error_summary = error_summary
        preview = error_summary[:10]
        more = "" if len(error_summary) <= 10 else f" (+{len(error_summary) - 10} more)"
        body = "; ".join(preview)
        super().__init__(
            f"input contract validation failed ({layer} layer): {body}{more}"
        )


class Hy3ConfigError(GeneratorError):
    """A required Hy3 environment variable is missing or empty.

    The message names the missing variable(s) but NEVER echoes any value.
    """


class Hy3APIError(GeneratorError):
    """The Hy3 API call failed (network, non-2xx, malformed payload).

    Attributes:
        status_code: HTTP status code if a response was received, else ``None``.
        response_text: full HTTP response body when available (for the smoke
            runner's ``http_response.txt`` artifact); may be ``None`` for network
            errors. Never contains the request API key.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message)


class ResponseParsingError(GeneratorError):
    """The Hy3 response text could not be parsed as a JSON object.

    Attributes:
        raw_text: the exact model output text (for the smoke runner's
            ``raw_response.txt`` artifact).
    """

    def __init__(self, message: str, *, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__(message)


class SpeechPlanStructuralError(GeneratorError):
    """The parsed speech plan failed JSON Schema structural validation.

    Attributes:
        plan_doc: the parsed dict that failed.
        error_summary: ``"<json_path>: <message>"`` lines from jsonschema.
        raw_text: the exact Hy3 response text (so the smoke runner can save
            ``raw_response.txt`` even when structural validation fails after the
            API has returned).
    """

    def __init__(
        self,
        plan_doc: dict,
        error_summary: list[str],
        *,
        raw_text: str,
    ) -> None:
        self.plan_doc = plan_doc
        self.error_summary = error_summary
        self.raw_text = raw_text
        preview = error_summary[:10]
        more = "" if len(error_summary) <= 10 else f" (+{len(error_summary) - 10} more)"
        body = "; ".join(preview)
        super().__init__(
            f"speech plan failed structural (JSON Schema) validation: {body}{more}"
        )


class SpeechPlanSemanticError(GeneratorError):
    """The parsed speech plan failed Pydantic cross-field semantic validation.

    Attributes:
        plan_doc: the parsed dict that failed.
        error_text: full ``str(pydantic.ValidationError)`` (rule tags such as
            "Rule 2 (segment reference integrity)" are already embedded by the
            frozen model layer).
        raw_text: the exact Hy3 response text (same rationale as
            :class:`SpeechPlanStructuralError`).
    """

    def __init__(
        self,
        plan_doc: dict,
        error_text: str,
        *,
        raw_text: str,
    ) -> None:
        self.plan_doc = plan_doc
        self.error_text = error_text
        self.raw_text = raw_text
        super().__init__(
            "speech plan failed semantic (Pydantic) validation: " + error_text
        )
