"""Programmatic JSON Schema validation entry points.

Loads ``schemas/teachintent_input.schema.json`` and
``schemas/speech_plan.schema.json`` and wraps them with Draft 2020-12
validators.  Per Rule 15 of docs/speech_plan_schema.md this layer carries the
structural constraints; cross-field semantic constraints live in the Pydantic
model layer (``teachintent.models``).

Known limitation: the schema directory is resolved relative to the repository
root, which works for development and test usage (editable install).  An
installed wheel does not ship ``schemas/``; a later phase may add a
force-include mapping plus an ``importlib.resources`` loader.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
INPUT_SCHEMA_PATH = SCHEMA_DIR / "teachintent_input.schema.json"
SPEECH_PLAN_SCHEMA_PATH = SCHEMA_DIR / "speech_plan.schema.json"

__all__ = [
    "load_input_schema",
    "load_speech_plan_schema",
    "get_input_validator",
    "get_speech_plan_validator",
    "validate_input_document",
    "validate_speech_plan_document",
    "iter_input_errors",
    "iter_speech_plan_errors",
]


@lru_cache(maxsize=None)
def load_input_schema() -> dict[str, Any]:
    """Load and return the TeachIntent input JSON Schema document."""
    with INPUT_SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def load_speech_plan_schema() -> dict[str, Any]:
    """Load and return the Speech Plan JSON Schema document."""
    with SPEECH_PLAN_SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def get_input_validator() -> Draft202012Validator:
    """Return a cached Draft 2020-12 validator for the input contract."""
    schema = load_input_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=None)
def get_speech_plan_validator() -> Draft202012Validator:
    """Return a cached Draft 2020-12 validator for the Speech Plan."""
    schema = load_speech_plan_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_input_document(document: Any) -> None:
    """Validate an input document; raise ``ValidationError`` on failure."""
    get_input_validator().validate(document)


def validate_speech_plan_document(document: Any) -> None:
    """Validate a speech plan document; raise ``ValidationError`` on failure."""
    get_speech_plan_validator().validate(document)


def iter_input_errors(document: Any) -> list[ValidationError]:
    """Return all structural validation errors for an input document."""
    return list(get_input_validator().iter_errors(document))


def iter_speech_plan_errors(document: Any) -> list[ValidationError]:
    """Return all structural validation errors for a speech plan document."""
    return list(get_speech_plan_validator().iter_errors(document))
