"""Validation entry points for the TeachIntent contracts.

Two complementary layers:

* :mod:`teachintent.validators.jsonschema_validation` — structural
  validation against ``schemas/*.schema.json`` (Draft 2020-12);
* :mod:`teachintent.models` — strict Pydantic models carrying the
  cross-field semantic validators (Rules 1/2/3/5/8/11/12 of
  docs/speech_plan_schema.md).
"""

from .jsonschema_validation import (
    get_input_validator,
    get_speech_plan_validator,
    iter_input_errors,
    iter_speech_plan_errors,
    load_input_schema,
    load_speech_plan_schema,
    validate_input_document,
    validate_speech_plan_document,
)

__all__ = [
    "get_input_validator",
    "get_speech_plan_validator",
    "iter_input_errors",
    "iter_speech_plan_errors",
    "load_input_schema",
    "load_speech_plan_schema",
    "validate_input_document",
    "validate_speech_plan_document",
]
